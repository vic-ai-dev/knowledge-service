"""数据库连接池管理（asyncpg）。

提供知识库库 (knowledge) 与向量库 (knowledge_rag) 的异步连接池，
以及 FastAPI 依赖注入函数。

用法:
    async with get_db_pool() as pool:
        async with pool.acquire() as conn:
            await conn.fetch("SELECT 1")
"""

from __future__ import annotations

from typing import AsyncGenerator

import asyncpg

from app.common.settings import get_settings
from app.common.log import get_logger

logger = get_logger(__name__)

# ── 全局池 ─────────────────────────────────────────────

_knowledge_pool: asyncpg.Pool | None = None
_rag_pool: asyncpg.Pool | None = None


async def _create_pool(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    min_size: int = 2,
    max_size: int = 10,
    label: str = "pool",
) -> asyncpg.Pool:
    """创建 asyncpg 连接池。"""
    try:
        pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=min_size,
            max_size=max_size,
        )
        logger.info(
            "db_pool_created",
            message=f"数据库连接池创建成功 [{label}]",
            metadata={"host": host, "port": port, "database": database, "min_size": min_size, "max_size": max_size},
        )
        return pool
    except asyncpg.PostgresError as e:
        logger.error(
            "db_pool_failed",
            error=str(e),
            message=f"数据库连接池创建失败 [{label}]",
            metadata={"host": host, "port": port, "database": database},
        )
        raise


async def init_db_pools() -> None:
    """在应用启动时初始化全部数据库连接池。"""
    global _knowledge_pool, _rag_pool
    settings = get_settings()

    # 知识库连接池 (knowledge)
    _knowledge_pool = await _create_pool(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.user,
        password=settings.database.password,
        database=settings.database.database,
        min_size=2,
        max_size=settings.database.max_connections,
        label="knowledge",
    )

    # 向量库连接池 (knowledge_rag)
    _rag_pool = await _create_pool(
        host=settings.vector_store.host,
        port=settings.vector_store.port,
        user=settings.vector_store.user,
        password=settings.vector_store.password,
        database=settings.vector_store.database,
        min_size=settings.vector_store.pool_min_size,
        max_size=settings.vector_store.pool_max_size,
        label="knowledge_rag",
    )


async def close_db_pools() -> None:
    """在应用关闭时关闭全部数据库连接池。"""
    global _knowledge_pool, _rag_pool

    if _knowledge_pool:
        await _knowledge_pool.close()
        _knowledge_pool = None
        logger.info("db_pool_closed", message="知识库连接池已关闭")

    if _rag_pool:
        await _rag_pool.close()
        _rag_pool = None
        logger.info("db_pool_closed", message="向量库连接池已关闭")


# ── 获取池 ─────────────────────────────────────────────


def get_knowledge_pool() -> asyncpg.Pool:
    """获取知识库连接池。"""
    if _knowledge_pool is None:
        raise RuntimeError("知识库连接池未初始化，请先调用 init_db_pools()")
    return _knowledge_pool


def get_rag_pool() -> asyncpg.Pool:
    """获取向量库连接池。"""
    if _rag_pool is None:
        raise RuntimeError("向量库连接池未初始化，请先调用 init_db_pools()")
    return _rag_pool


# ── FastAPI 依赖 ───────────────────────────────────────


async def get_kb_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI 依赖：获取知识库连接。"""
    pool = get_knowledge_pool()
    async with pool.acquire() as conn:
        yield conn


async def get_rag_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI 依赖：获取向量库连接。"""
    pool = get_rag_pool()
    async with pool.acquire() as conn:
        yield conn


__all__ = [
    "init_db_pools",
    "close_db_pools",
    "get_knowledge_pool",
    "get_rag_pool",
    "get_kb_conn",
    "get_rag_conn",
]
