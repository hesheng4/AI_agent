"""限流抽象层 - 支持 memory / redis 双后端，通过配置切换

设计要点：
- RateLimiterBackend 定义统一 async 接口
- MemoryRateLimiter：进程内滑动窗口，单实例
- RedisRateLimiter：用 Redis ZSET 实现分布式滑动窗口，Lua 脚本保证原子性
- Redis 不可用时按 RATE_LIMIT_FALLBACK 降级（allow 放行 / deny 拒绝）
- 全局 rate_limiter 由工厂按配置创建，向后兼容
"""

import time
import uuid
from abc import ABC, abstractmethod

from fastapi import HTTPException, Request, status

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("rate_limit")


class RateLimiterBackend(ABC):
    """限流后端抽象基类"""

    @abstractmethod
    async def check_rate_limit(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> bool:
        """检查并记录请求，返回是否允许"""

    @abstractmethod
    async def get_remaining(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> int:
        """获取窗口内剩余次数（不记录请求）"""

    @abstractmethod
    async def reset(self, user_id: str) -> None:
        """重置用户计数"""


class MemoryRateLimiter(RateLimiterBackend):
    """内存限流器（开发用，单实例）"""

    def __init__(self, max_users: int = 100_000):
        # {user_id: {"requests": [timestamp]}}
        self._requests: dict[str, dict] = {}
        self._max_users = max_users

    def _global_cleanup(self, window: int = 60):
        """全量清理：删除所有窗口内无有效请求的用户

        判定标准为该用户是否还存在 window 内的有效请求——只要有一条未过期就保留，
        避免旧版只看最后一条导致的内存只增不减。
        """
        now = time.time()
        expired_users = []
        for user_id, data in self._requests.items():
            reqs = data["requests"]
            # 过滤出仍有效的请求
            valid = [ts for ts in reqs if now - ts < window]
            if not valid:
                expired_users.append(user_id)
            else:
                data["requests"] = valid
        for user_id in expired_users:
            del self._requests[user_id]

    def _cleanup_old_requests(self, user_id: str, window: int = 60):
        if user_id not in self._requests:
            return
        now = time.time()
        self._requests[user_id]["requests"] = [
            ts for ts in self._requests[user_id]["requests"] if now - ts < window
        ]

    async def check_rate_limit(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> bool:
        if len(self._requests) > self._max_users:
            self._global_cleanup(window)
        if user_id not in self._requests:
            self._requests[user_id] = {"requests": []}
        self._cleanup_old_requests(user_id, window)
        current_count = len(self._requests[user_id]["requests"])
        if current_count >= max_requests:
            logger.warning(
                f"用户 {user_id} 触发速率限制: {current_count}/{max_requests}"
            )
            return False
        self._requests[user_id]["requests"].append(time.time())
        return True

    async def get_remaining(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> int:
        if user_id not in self._requests:
            return max_requests
        self._cleanup_old_requests(user_id, window)
        current_count = len(self._requests[user_id]["requests"])
        return max(0, max_requests - current_count)

    async def reset(self, user_id: str) -> None:
        if user_id in self._requests:
            del self._requests[user_id]


# 滑动窗口 Lua 脚本：ZREMRANGEBYSCORE 清旧 → ZCARD 计数 → 未超则 ZADD
# 原子执行，避免并发竞态
# 时间单位约定：score 用毫秒（now_ms），window 入参为秒，Lua 内转毫秒相减
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2]) * 1000
local max_req = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= max_req then
    return 0
end
redis.call('ZADD', key, now_ms, member)
redis.call('EXPIRE', key, tonumber(ARGV[2]))
return 1
"""

# 剩余次数查询 Lua：清旧 → ZCARD → 返回 max - count（不记录请求）
_REMAINING_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2]) * 1000
local max_req = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local count = redis.call('ZCARD', key)
local remaining = max_req - count
if remaining < 0 then remaining = 0 end
return remaining
"""


class RedisRateLimiter(RateLimiterBackend):
    """Redis 分布式限流器（生产用，多实例共享计数）

    用 ZSET 滑动窗口 + Lua 脚本保证原子性。
    连接不可用时按 RATE_LIMIT_FALLBACK 降级。
    """

    def __init__(self, key_prefix: str = "ratelimit:", fallback: str = "allow"):
        self.key_prefix = key_prefix
        self.fallback = fallback
        self._check_script = None
        self._remaining_script = None

    def _redis(self):
        from app.core.redis_client import get_redis

        return get_redis()

    def _key(self, user_id: str) -> str:
        return f"{self.key_prefix}{user_id}"

    def _fallback_decision(self) -> bool:
        """Redis 不可用时的降级决策"""
        if self.fallback == "deny":
            logger.warning("Redis 不可用且降级策略为 deny，拒绝请求")
            return False
        logger.warning("Redis 不可用且降级策略为 allow，放行请求")
        return True

    async def check_rate_limit(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> bool:
        client = self._redis()
        if client is None:
            return self._fallback_decision()
        try:
            if self._check_script is None:
                self._check_script = client.register_script(_SLIDING_WINDOW_LUA)
            now_ms = int(time.time() * 1000)
            member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
            allowed = await self._check_script(
                keys=[self._key(user_id)],
                args=[now_ms, window, max_requests, member],
            )
            # Lua 返回 int 0/1
            if int(allowed) == 0:
                logger.warning(f"用户 {user_id} 触发速率限制: {max_requests}/{window}s")
                return False
            return True
        except Exception as e:
            logger.warning(f"Redis 限流检查失败，降级: {e}")
            return self._fallback_decision()

    async def get_remaining(
        self, user_id: str, max_requests: int = 60, window: int = 60
    ) -> int:
        client = self._redis()
        if client is None:
            # 降级时返回 max_requests（表示未受限），与 allow 策略一致
            return max_requests if self.fallback == "allow" else 0
        try:
            if self._remaining_script is None:
                self._remaining_script = client.register_script(_REMAINING_LUA)
            now_ms = int(time.time() * 1000)
            remaining = await self._remaining_script(
                keys=[self._key(user_id)],
                args=[now_ms, window, max_requests],
            )
            return int(remaining)
        except Exception as e:
            logger.warning(f"Redis 限流剩余查询失败，降级: {e}")
            return max_requests if self.fallback == "allow" else 0

    async def reset(self, user_id: str) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            await client.delete(self._key(user_id))
        except Exception as e:
            logger.warning(f"Redis 限流重置失败，静默跳过: {e}")


# 向后兼容别名：旧代码 `from app.core.rate_limit import RateLimiter`
RateLimiter = MemoryRateLimiter


def _create_rate_limiter() -> RateLimiterBackend:
    """根据配置创建限流后端实例

    配置异常时回退到 MemoryRateLimiter，避免进程启动失败。
    """
    try:
        settings = get_settings()
        if settings.RATE_LIMIT_BACKEND == "redis":
            logger.info("使用 Redis 限流后端")
            return RedisRateLimiter(
                key_prefix="ratelimit:",
                fallback=settings.RATE_LIMIT_FALLBACK,
            )
        logger.info("使用内存限流后端")
        return MemoryRateLimiter()
    except Exception as e:
        logger.warning(f"限流后端初始化失败，回退到 MemoryRateLimiter: {e}")
        return MemoryRateLimiter()


# 全局限流实例（向后兼容：from app.core.rate_limit import rate_limiter）
rate_limiter = _create_rate_limiter()

# 不同套餐的限制配置
RATE_LIMITS = {
    "free": {"max_requests": 10, "window": 60},  # 10次/分钟
    "basic": {"max_requests": 30, "window": 60},  # 30次/分钟
    "pro": {"max_requests": 100, "window": 60},  # 100次/分钟
    "enterprise": {"max_requests": 1000, "window": 60},  # 1000次/分钟
}


def get_rate_limit_config(plan: str) -> dict:
    """获取套餐的速率限制配置"""
    return RATE_LIMITS.get(plan, RATE_LIMITS["free"])


async def check_rate_limit_middleware(
    request: Request, user_id: str, plan: str = "free"
):
    """速率限制检查中间件"""
    config = get_rate_limit_config(plan)

    if not await rate_limiter.check_rate_limit(
        user_id, max_requests=config["max_requests"], window=config["window"]
    ):
        remaining = await rate_limiter.get_remaining(
            user_id, config["max_requests"], config["window"]
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": config["window"],
                "remaining": remaining,
            },
        )

    return True
