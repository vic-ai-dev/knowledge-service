"""E3 — 系统配置与统计端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.core.database_sa import get_kb_session, get_rag_session
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import DocumentChunkRepository
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
    kb_session: AsyncSession = Depends(get_kb_session),
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """获取系统统计信息（文档数、分块数等）。"""
    doc_repo = DocumentRepository(kb_session)
    chunk_repo = DocumentChunkRepository(rag_session)

    stats = await doc_repo.get_stats()
    chunk_count = await chunk_repo.get_total_count()

    return {
        "total_documents": stats["total_documents"],
        "total_chunks": chunk_count,
        "total_categories": len(stats["by_category"]),
        "total_size_bytes": stats["total_size_bytes"],
        "by_category": stats["by_category"],
        "by_language": stats["by_language"],
        "by_type": stats.get("by_type", {}),
    }


__all__ = ["router"]
