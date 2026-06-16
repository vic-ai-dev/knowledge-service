"""Alembic env.py — 多数据库迁移支持 (knowledge + knowledge_rag).

使用同步 psycopg2 驱动，兼容 Alembic 原生连接 API。
数据库配置从 settings.yaml 读取，不在 ini 中硬编码凭证。
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# ── 导入所有 ORM 模型以注册 Metadata ──
from app.models.base import KnowledgeBase, RagBase
import app.models  # noqa: F401 — 确保所有模型被导入

# ── 导入 Settings ──
from app.core.settings import get_settings

config = context.config

# fileConfig disabled — logging configured by app

settings = get_settings()


def _build_dsn(
    host: str, port: int, user: str, password: str, database: str
) -> str:
    """构建同步 psycopg2 DSN。"""
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


# ── 多数据库目标 Metadata ──────────────────────────────
_DB_URLS = {
    "knowledge": _build_dsn(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.user,
        password=settings.database.password,
        database=settings.database.database,
    ),
    "rag": _build_dsn(
        host=settings.vector_store.host,
        port=settings.vector_store.port,
        user=settings.vector_store.user,
        password=settings.vector_store.password,
        database=settings.vector_store.database,
    ),
}

_TARGET_METADATA = {
    "knowledge": KnowledgeBase.metadata,
    "rag": RagBase.metadata,
}


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本至标准输出。"""
    for db_name, metadata in _TARGET_METADATA.items():
        context.configure(
            url=_DB_URLS[db_name],
            target_metadata=metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            version_table=f"alembic_version_{db_name}",
        )
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：逐个数据库执行迁移。"""
    for db_name, metadata in _TARGET_METADATA.items():
        engine = create_engine(
            _DB_URLS[db_name],
            poolclass=pool.NullPool,
        )
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=metadata,
                version_table=f"alembic_version_{db_name}",
            )
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
