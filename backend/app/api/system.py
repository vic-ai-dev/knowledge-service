"""E3 — 系统配置与统计端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from asyncpg import Connection

from app.core.settings import get_settings
from app.core.database import get_kb_conn, get_rag_conn
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["system"])


@router.get("/system/config")
async def get_config():
    """获取当前系统配置（隐藏敏感字段）。"""
    settings = get_settings()
    return {
        "server": {"port": settings.server.port, "max_file_size": settings.server.max_file_size, "allowed_extensions": settings.server.allowed_extensions},
        "database": {"host": settings.database.host, "port": settings.database.port, "database": settings.database.database},
        "vector_store": {"backend": settings.vector_store.backend, "host": settings.vector_store.host, "port": settings.vector_store.port, "database": settings.vector_store.database},
        "llm": {"provider": settings.llm.provider, "model": settings.llm.model},
        "embedding": {"provider": settings.embedding.provider, "model": settings.embedding.model},
        "rerank": {"provider": settings.rerank.provider, "model": settings.rerank.model, "enabled": settings.rerank.enabled},
        "retrieval": {"sparse_backend": settings.retrieval.sparse_backend, "fusion_algorithm": settings.retrieval.fusion_algorithm},
    }


@router.get("/system/stats")
async def get_system_stats(
    kb_conn: Connection = Depends(get_kb_conn),
    rag_conn: Connection = Depends(get_rag_conn),
):
    """获取系统统计信息（文档数、分块数等）。"""
    # 文档总数 + 总大小
    doc_row = await kb_conn.fetchrow("""
        SELECT
            COUNT(*)::int AS total_documents,
            COALESCE(SUM(file_size), 0)::bigint AS total_size_bytes
        FROM documents
        WHERE is_deleted = FALSE
    """)
    total_documents = doc_row["total_documents"] if doc_row else 0
    total_size_bytes = doc_row["total_size_bytes"] if doc_row else 0

    # Chunk 总数
    chunk_row = await rag_conn.fetchrow("SELECT COUNT(*)::int AS total_chunks FROM document_chunks")
    total_chunks = chunk_row["total_chunks"] if chunk_row else 0

    # 集合数
    col_row = await rag_conn.fetchrow("SELECT COUNT(*)::int AS total_collections FROM collections")
    total_collections = col_row["total_collections"] if col_row else 0

    # 分类统计
    cat_rows = await kb_conn.fetch("""
        SELECT category, COUNT(*)::int AS cnt
        FROM documents
        WHERE is_deleted = FALSE
        GROUP BY category
    """)
    by_category = {r["category"]: r["cnt"] for r in cat_rows}

    # 语言统计
    lang_rows = await kb_conn.fetch("""
        SELECT language, COUNT(*)::int AS cnt
        FROM documents
        WHERE is_deleted = FALSE
        GROUP BY language
    """)
    by_language = {r["language"]: r["cnt"] for r in lang_rows}

    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "total_collections": total_collections,
        "total_categories": len(by_category),
        "total_size_bytes": total_size_bytes,
        "by_category": by_category,
        "by_language": by_language,
    }


__all__ = ["router"]
