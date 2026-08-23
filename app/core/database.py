from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 连接池配置：
# - pool_pre_ping: 防止使用已被服务端断开的空闲连接
# - pool_recycle: 主动回收长连接，避免数据库端 max_lifetime 限制
# - SQLite 不支持连接池参数，仅对 PostgreSQL/MySQL 生效
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        except Exception:
            # commit/flush 失败后必须 rollback，否则 session 处于
            # "transaction in error" 状态，后续复用会持续报错
            await session.rollback()
            raise
        finally:
            await session.close()


def get_async_engine():
    """返回全局 engine（供 health check 等场景取用）"""
    return engine


async def reset_engine(new_url: str | None = None) -> None:
    """重置全局 engine（主要供测试隔离使用）

    传入 new_url 则切换数据库 URL；不传则按当前 settings 重建。
    """
    global engine, async_session
    import logging

    logger = logging.getLogger("app.core.database")

    try:
        await engine.dispose()
    except Exception as e:
        logger.warning(f"reset_engine: 关闭旧 engine 失败: {e}")

    url = new_url or settings.DATABASE_URL
    # 修复：补回 pool_pre_ping 和 pool_recycle 配置，与模块顶层 engine 一致
    engine = create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
