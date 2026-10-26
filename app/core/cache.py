"""缓存抽象层 - 支持 memory / redis 双后端，通过配置切换

设计要点：
- CacheBackend 定义统一 async 接口，业务层无感知后端切换
- MemoryCache：进程内，单实例开发用
- RedisCache：分布式，多实例生产用；连接不可用时优雅降级（get 返回 None，set 静默）
- _make_key 保持同步（纯计算），供上层生成 key
- 全局 cache 实例由工厂按配置创建，向后兼容 `from app.core.cache import cache`
"""

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("cache")


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    def _make_key(self, prefix: str, params: dict[str, Any]) -> str:
        """根据前缀和参数生成缓存 key（同步，纯计算）"""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """获取缓存，未命中返回 None"""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """写入缓存"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除缓存"""

    @abstractmethod
    async def clear(self, prefix: str | None = None) -> int:
        """清空缓存，可按前缀；返回清除条目数"""

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """缓存统计"""


# 缓存 key 哈希长度：12 字符（48 bit），万级条目下碰撞概率可忽略
CACHE_KEY_HASH_LENGTH = 12


def _stable_repr(obj: Any) -> str:
    """生成确定性序列化字符串，用于缓存 key 计算。

    优先用 json.dumps（确定性、sort_keys、跨进程一致）；遇到不可 JSON
    序列化的对象（自定义类、Pydantic 模型、datetime 等）回退到：
    类型限定名 + 内容哈希，避免 `str()` 默认 `<X object at 0x...>`
    带内存地址导致语义相同的调用永远 cache miss。
    """
    try:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        # json 失败（循环引用等）：用类型名 + repr 的哈希兜底
        type_name = f"{type(obj).__module__}.{type(obj).__qualname__}"
        try:
            content = repr(obj)
        except Exception:
            content = "<unreprable>"
        return f"{type_name}:{hashlib.md5(content.encode()).hexdigest()[:16]}"


def _hash_key(prefix: str, params: dict[str, Any]) -> str:
    """统一的 key 生成逻辑：prefix:md5(stable_repr(params))[:CACHE_KEY_HASH_LENGTH]"""
    param_str = _stable_repr(params)
    hash_val = hashlib.md5(param_str.encode()).hexdigest()[:CACHE_KEY_HASH_LENGTH]
    return f"{prefix}:{hash_val}"


class MemoryCache(CacheBackend):
    """内存缓存（开发用，单实例）

    过期条目清理策略：
    1. 被动清理：get 时检查单条过期
    2. 容量触发：set 时超 max_size 触发批量清理
    3. 周期触发：set 时距上次清理超过 CLEANUP_INTERVAL_SECONDS 则触发
       避免大量写入后不再读取导致内存不释放
    """

    # 周期清理间隔（秒）
    CLEANUP_INTERVAL_SECONDS = 60

    def __init__(self, default_ttl: int = 3600, max_size: int = 10000):
        self._cache: dict[str, dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._last_cleanup: datetime = datetime.now()

    def _make_key(self, prefix: str, params: dict[str, Any]) -> str:
        return _hash_key(prefix, params)

    async def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        entry = self._cache[key]
        if datetime.now() > entry["expires"]:
            del self._cache[key]
            logger.debug(f"缓存过期: {key}")
            return None
        logger.debug(f"缓存命中: {key}")
        return entry["value"]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        # 容量控制：超限时先清过期，仍满则淘汰最旧
        if len(self._cache) >= self.max_size:
            self._evict_expired()
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
        # 周期清理：距上次清理超过间隔则触发
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() >= self.CLEANUP_INTERVAL_SECONDS:
            self._evict_expired()
            self._last_cleanup = now
        # ttl=0 / None 均视为"用默认 TTL"，与 Redis SET EX 行为对齐
        # （Redis EX=0 会报错；MemoryCache 下 0 TTL 写入后立即过期属语义陷阱）
        effective_ttl = ttl if ttl else self.default_ttl
        self._cache[key] = {
            "value": value,
            "expires": now + timedelta(seconds=effective_ttl),
            "created": now,
        }
        logger.debug(f"缓存写入: {key}, TTL={effective_ttl}s")

    def _evict_expired(self) -> None:
        now = datetime.now()
        expired_keys = [k for k, v in self._cache.items() if now > v["expires"]]
        for k in expired_keys:
            del self._cache[k]

    async def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"缓存删除: {key}")

    async def clear(self, prefix: str | None = None) -> int:
        if prefix is None:
            count = len(self._cache)
            self._cache.clear()
        else:
            keys = [k for k in self._cache if k.startswith(prefix)]
            count = len(keys)
            for k in keys:
                del self._cache[k]
        logger.info(f"清空缓存: {count}条")
        return count

    async def stats(self) -> dict[str, Any]:
        now = datetime.now()
        active = sum(1 for v in self._cache.values() if now <= v["expires"])
        expired = len(self._cache) - active
        return {
            "backend": "memory",
            "total": len(self._cache),
            "active": active,
            "expired": expired,
        }


class RedisCache(CacheBackend):
    """Redis 分布式缓存（生产用，多实例共享）

    value 用 JSON 序列化，外层包装类型标记以正确还原。
    连接不可用时优雅降级：get 返回 None（miss），set/delete/clear 静默跳过。
    """

    def __init__(self, key_prefix: str = "rap:", default_ttl: int = 1800):
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

    def _redis(self) -> Any:
        # 延迟获取，避免模块加载时 Redis 未初始化
        from app.core.redis_client import get_redis

        return get_redis()

    def _full_key(self, key: str) -> str:
        # 用户传入的 key 已含前缀（如 llm:abc123），再加全局前缀避免与其他服务冲突
        return f"{self.key_prefix}{key}"

    def _make_key(self, prefix: str, params: dict[str, Any]) -> str:
        return _hash_key(prefix, params)

    async def get(self, key: str) -> Any | None:
        client = self._redis()
        if client is None:
            return None
        try:
            raw = await client.get(self._full_key(key))
            if raw is None:
                return None
            logger.debug(f"Redis 缓存命中: {key}")
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get 失败，降级为 miss: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
            await client.set(self._full_key(key), payload, ex=ttl or self.default_ttl)
            logger.debug(f"Redis 缓存写入: {key}, TTL={ttl}s")
        except Exception as e:
            logger.warning(f"Redis set 失败，静默跳过: {e}")

    async def delete(self, key: str) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            await client.delete(self._full_key(key))
        except Exception as e:
            logger.warning(f"Redis delete 失败，静默跳过: {e}")

    async def clear(self, prefix: str | None = None) -> int:
        """按前缀清空。用 SCAN 避免阻塞 Redis（不用 KEYS）"""
        client = self._redis()
        if client is None:
            return 0
        pattern = f"{self.key_prefix}{prefix}*" if prefix else f"{self.key_prefix}*"
        count = 0
        try:
            async for batch in client.scan_iter(match=pattern, count=200):
                await client.delete(batch)
                count += 1
            logger.info(f"Redis 清空缓存: {count}条")
        except Exception as e:
            logger.warning(f"Redis clear 失败，静默跳过: {e}")
        return count

    async def stats(self) -> dict[str, Any]:
        client = self._redis()
        if client is None:
            return {
                "backend": "redis(unavailable)",
                "total": 0,
                "active": 0,
                "expired": 0,
            }
        try:
            # 近似统计：DBSIZE 给总数，无过期概念
            total = await client.dbsize()
            return {
                "backend": "redis",
                "total": total,
                "active": total,
                "expired": 0,
            }
        except Exception as e:
            logger.warning(f"Redis stats 失败: {e}")
            return {
                "backend": "redis(unavailable)",
                "total": 0,
                "active": 0,
                "expired": 0,
            }


def _create_cache() -> CacheBackend:
    """根据配置创建缓存后端实例

    配置异常或后端初始化失败时回退到 MemoryCache，避免进程启动失败。
    """
    try:
        settings = get_settings()
        if settings.CACHE_BACKEND == "redis":
            logger.info("使用 Redis 缓存后端")
            return RedisCache(
                key_prefix=settings.CACHE_KEY_PREFIX,
                default_ttl=settings.CACHE_DEFAULT_TTL,
            )
        logger.info("使用内存缓存后端")
        return MemoryCache(
            default_ttl=settings.CACHE_DEFAULT_TTL,
            max_size=settings.CACHE_MAX_SIZE,
        )
    except Exception as e:
        logger.warning(f"缓存后端初始化失败，回退到 MemoryCache: {e}")
        return MemoryCache()


# 全局缓存实例（向后兼容：from app.core.cache import cache）
cache = _create_cache()


def cached(
    prefix: str, ttl: int | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """缓存装饰器（async 函数专用）

    实例方法检测：通过 inspect.signature 的第一个参数名是否为 self/cls 判断。
    实例方法会跳过 args[0] 以避免每个实例的缓存互不共享。

    注意（S4 安全纪律）：缓存 key 由 prefix + 参数的 _stable_repr 构成，
    **不含用户身份**。仅可用于无用户维度的纯派生数据（如模板解析结果）；
    用户态数据请显式调用 cache.get/set 并在 key 中带上 user_id。
    """
    import inspect

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # 预先判断是否为实例方法（第一个参数名为 self 或 cls）
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
            is_method = bool(params) and params[0].name in ("self", "cls")
        except (ValueError, TypeError):
            is_method = False

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 实例方法跳过 args[0]
            cache_args = args[1:] if is_method and args else args
            # S4: 用 _stable_repr 替代 str()，避免自定义对象内存地址导致 cache miss
            cache_params = {
                "args": _stable_repr(cache_args),
                "kwargs": _stable_repr(kwargs),
            }
            cache_key = cache._make_key(prefix, cache_params)

            result = await cache.get(cache_key)
            if result is not None:
                return result

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result

        wrapper.cache_clear = lambda: cache.clear(prefix)  # type: ignore[attr-defined] # 测试通过该动态属性清缓存
        return wrapper

    return decorator
