"""Redis 连接池管理

在应用 lifespan 启动时调用 init_redis，关闭时调用 close_redis。
其他模块通过 get_redis() 获取已初始化的异步客户端；未初始化时返回 None，
调用方应据此做优雅降级（缓存 miss / 限流放行）。
"""

from redis.asyncio import ConnectionPool, Redis

from app.utils.logger import get_logger

logger = get_logger("redis")

_pool: ConnectionPool | None = None
_redis: Redis | None = None


async def init_redis(url: str) -> None:
    """初始化 Redis 连接池（lifespan startup 调用）"""
    global _pool, _redis
    if _redis is not None:
        return
    _pool = ConnectionPool.from_url(
        url,
        max_connections=50,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        retry_on_timeout=True,
        decode_responses=True,  # 返回 str 而非 bytes，简化上层处理
    )
    _redis = Redis(connection_pool=_pool)
    try:
        await _redis.ping()
        logger.info(f"Redis 连接成功: {url}")
    except Exception as e:
        logger.error(f"Redis 连接失败: {e}，缓存/限流将降级")
        await close_redis()


async def close_redis() -> None:
    """关闭 Redis 连接池（lifespan shutdown 调用）"""
    global _pool, _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
    logger.info("Redis 连接已关闭")


def get_redis() -> Redis | None:
    """获取 Redis 客户端，未初始化或已关闭时返回 None"""
    return _redis


# 兼容别名：部分旧代码/health 端点用 get_redis_client() 命名
get_redis_client = get_redis
