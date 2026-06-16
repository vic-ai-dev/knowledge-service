"""SQLAlchemy 2.0 async 引擎与会话管理。

遵循两数据库模式：
- `knowledge` 库：业务数据（documents, ingestion_history, query_traces 等）
- `knowledge_rag` 库：向量 + 全文检索数据（document_chunks）

用法:
    async with get_async_session('knowledge') as session:
        await session.execute(...)
"""

from __future__ import annotations

from typing import AsyncGenerator, Literal

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings
from app.common.log import get_logger

import time
from sqlalchemy import event

_sql_timings: dict[int, float] = {}


def _install_sql_listeners(engine) -> None:
    """Install MyBatis-style SQL logging on the engine."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        _sql_timings[id(conn)] = time.monotonic()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        start = _sql_timings.pop(id(conn), None)
        duration_ms = (time.monotonic() - start) * 1000 if start else 0.0
        params_str = str(parameters)
        if len(params_str) > 300:
            params_str = params_str[:300] + "..."
        stmt = statement
        if len(stmt) > 2000:
        stmt = stmt.replace("\\n", " ").replace("\\r", "")
            stmt = stmt[:2000] + "..."
        logger.info(
            "sql",
            message=f"[SQL] {stmt}",
            params=params_str,
            duration_ms=f"{duration_ms:.2f}",
        )

logger = get_logger(__name__)

# ── 全局引擎 ──────────────────────────────────────────
_kb_engine = None
_rag_engine = None
_kb_session_factory = None
_rag_session_factory = None

DbName = Literal["knowledge", "rag"]


def _build_async_dsn(
    host: str, port: int, user: str, password: str, database: str
) -> str:
    """构建 asyncpg DSN。"""
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def init_sa_engine() -> None:
    """初始化 SQLAlchemy 异步引擎和会话工厂。"""
    global _kb_engine, _rag_engine, _kb_session_factory, _rag_session_factory
    settings = get_settings()

    # knowledge 库
    kb_dsn = _build_async_dsn(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.user,
        password=settings.database.password,
        database=settings.database.database,
    )
    _kb_engine = create_async_engine(
        kb_dsn,
        pool_size=settings.database.max_connections,
        max_overflow=5,
        pool_pre_ping=True,
        echo=False,
    )
    _install_sql_listeners(_kb_engine)

    _kb_session_factory = async_sessionmaker(
        _kb_engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info(
        "sa_engine_created",
        message=f"SQLAlchemy 引擎已创建 [knowledge]",
        metadata={"dsn": kb_dsn.replace(settings.database.password, "****")},
    )

    # knowledge_rag 库
    rag_dsn = _build_async_dsn(
        host=settings.vector_store.host,
        port=settings.vector_store.port,
        user=settings.vector_store.user,
        password=settings.vector_store.password,
        database=settings.vector_store.database,
    )
    _rag_engine = create_async_engine(
        rag_dsn,
        pool_size=settings.vector_store.pool_max_size,
        max_overflow=5,
        pool_pre_ping=True,
        echo=False,
    )
    _install_sql_listeners(_rag_engine)

    _rag_session_factory = async_sessionmaker(
        _rag_engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info(
        "sa_engine_created",
        message="SQLAlchemy 引擎已创建 [knowledge_rag]",
        metadata={"dsn": rag_dsn.replace(settings.vector_store.password, "****")},
    )


async def close_sa_engine() -> None:
    """关闭 SQLAlchemy 引擎。"""
    global _kb_engine, _rag_engine, _kb_session_factory, _rag_session_factory

    if _kb_engine:
        await _kb_engine.dispose()
        _kb_engine = None
        _kb_session_factory = None
        logger.info("sa_engine_closed", message="SQLAlchemy 引擎已关闭 [knowledge]")

    if _rag_engine:
        await _rag_engine.dispose()
        _rag_engine = None
        _rag_session_factory = None
        logger.info("sa_engine_closed", message="SQLAlchemy 引擎已关闭 [knowledge_rag]")


# ── 会话工厂获取 ──────────────────────────────────────


def get_session_factory(db: DbName = "knowledge") -> async_sessionmaker[AsyncSession]:
    """获取指定数据库的会话工厂。"""
    if db == "knowledge":
        if _kb_session_factory is None:
            raise RuntimeError("knowledge 库会话工厂未初始化")
        return _kb_session_factory
    elif db == "rag":
        if _rag_session_factory is None:
            raise RuntimeError("knowledge_rag 库会话工厂未初始化")
        return _rag_session_factory
    else:
        raise ValueError(f"未知数据库: {db}")


# ── FastAPI 依赖 ──────────────────────────────────────


async def get_kb_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 获取 knowledge 库会话。"""
    factory = get_session_factory("knowledge")
    async with factory() as session:
        yield session


async def get_rag_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 获取 knowledge_rag 库会话。"""
    factory = get_session_factory("rag")
    async with factory() as session:
        yield session


__all__ = [
    "init_sa_engine",
    "close_sa_engine",
    "get_session_factory",
    "get_kb_session",
    "get_rag_session",
    "DbName",
]
