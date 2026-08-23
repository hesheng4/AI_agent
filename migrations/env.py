"""Alembic 迁移环境（async 版）

适配项目的 async engine（aiosqlite / asyncpg）。
- 从 app.config 读取 DATABASE_URL，自动转换为同步驱动供 Alembic 离线/在线使用
- 从 app.models 导入 Base.metadata 作为 target_metadata
- 启用 render_as_batch=True，支持 SQLite 的 ALTER TABLE 限制（batch 模式重建表）
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata

# 加载项目配置与模型
from app.config import get_settings
from app.core.database import Base

config = context.config

# 从应用配置注入数据库 URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本，不连接数据库

    适用于 CI 生成迁移脚本审查，或无数据库环境生成 DDL。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite batch 模式
        compare_type=True,  # 比较列类型变化
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在已建立的连接上执行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式（async）：用 async engine 建立连接后执行迁移"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口：调度 async 迁移"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
