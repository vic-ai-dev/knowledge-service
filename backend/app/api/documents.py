"""E12 — 文档管理 API（文档 CRUD、批量删除、重新索引、集合管理、文档统计）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session, get_rag_session
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import DocumentChunkRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    DocumentStatsResponse,
)
from app.models.document import Document
from app.common.log import get_logger
from app.schemas.document import DocumentResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def _doc_to_response(doc: Document) -> dict:
    return DocumentResponse(
        id=str(doc.id),
        source_path=doc.source_path,
        title=doc.title,
        category=doc.category,
        language=doc.language,
        doc_type=doc.doc_type,
        file_size=doc.file_size,
        file_hash=doc.file_hash,
        chunk_count=doc.chunk_count,
        image_count=doc.image_count,
        ingested_at=doc.ingested_at.isoformat() if doc.ingested_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
        is_deleted=doc.is_deleted,
    ).model_dump()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    kb_session: AsyncSession = Depends(get_kb_session),
    category: str | None = Query(None),
    language: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """文档中心 — 文档库列表。"""
    repo = DocumentRepository(kb_session)
    rows, total = await repo.find_all_active(
        category=category,
        language=language,
        page=page,
        page_size=page_size,
    )
    items = [_doc_to_response(d) for d in rows]
    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取单个文档详情。"""
    repo = DocumentRepository(kb_session)
    doc = await repo.find_by_id(doc_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _doc_to_response(doc)


@router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    rag_session: AsyncSession = Depends(get_rag_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取指定文档的分块列表。"""
    repo = DocumentChunkRepository(rag_session)
    rows, total = await repo.find_by_document(doc_id, page=page, page_size=page_size)
    items = []
    for c in rows:
        items.append({
            "id": str(c.id),
            "doc_id": str(c.doc_id) if c.doc_id else None,
            "chunk_index": c.chunk_index,
            "text": c.text,
            "metadata": c.metadata_ if c.metadata_ else {},
            "source_path": c.source_path,
            "token_count": c.token_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/{doc_id}")
async def update_document(
    doc_id: str,
    body: DocumentUpdate,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """更新文档 metadata。"""
    repo = DocumentRepository(kb_session)
    doc = await repo.find_by_id(doc_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=404, detail="文档不存在")

    update_kwargs = {k: v for k, v in body.model_dump(exclude_none=True).items() if v is not None}
    if update_kwargs:
        await repo.update(doc, **update_kwargs)
        await kb_session.commit()

    logger.info(
        "document_updated",
        message="文档已更新",
        metadata={"doc_id": doc_id, **update_kwargs},
    )
    return {"status": "updated", "doc_id": doc_id}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """删除单个文档（同时删除向量和 BM25 索引）。"""
    doc_repo = DocumentRepository(kb_session)
    chunk_repo = DocumentChunkRepository(rag_session)

    deleted = await doc_repo.soft_delete(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在或已删除")

    await chunk_repo.delete_by_document(doc_id)
    await kb_session.commit()
    await rag_session.commit()

    logger.info(
        "document_deleted",
        message="文档已删除",
        metadata={"doc_id": doc_id},
    )
    return {"status": "deleted", "doc_id": doc_id}


@router.post("/{doc_id}/reindex")
async def reindex_document(doc_id: str):
    """重新索引指定文档。"""
    # TODO(E12): 触发 IngestionPipeline 重新处理该文档
    logger.info(
        "document_reindex",
        message="文档重新索引已触发",
        metadata={"doc_id": doc_id},
    )
    return {"status": "reindexing", "doc_id": doc_id}


@router.post("/batch-delete")
async def batch_delete_documents(
    body: dict,
    kb_session: AsyncSession = Depends(get_kb_session),
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """批量删除文档。"""
    doc_ids = body.get("ids", [])
    if not doc_ids:
        raise HTTPException(status_code=400, detail="请提供要删除的文档 ID 列表")

    doc_repo = DocumentRepository(kb_session)
    chunk_repo = DocumentChunkRepository(rag_session)

    count = await doc_repo.batch_soft_delete(doc_ids)
    await chunk_repo.batch_delete_by_document(doc_ids)
    await kb_session.commit()
    await rag_session.commit()

    logger.info(
        "documents_batch_deleted",
        message="批量删除文档",
        metadata={"count": count},
    )
    return {"status": "deleted", "doc_ids": doc_ids, "count": count}


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    kb_session: AsyncSession = Depends(get_kb_session),
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """文档统计概览。"""
    doc_repo = DocumentRepository(kb_session)
    chunk_repo = DocumentChunkRepository(rag_session)

    stats = await doc_repo.get_stats()
    chunk_count = await chunk_repo.get_total_count()

    return DocumentStatsResponse(
        total_documents=stats["total_documents"],
        total_chunks=chunk_count,
        total_categories=len(stats["by_category"]),
        total_size_bytes=stats["total_size_bytes"],
        by_category=stats["by_category"],
        by_language=stats["by_language"],
        by_type=stats.get("by_type", {}),
    )


__all__ = ["router"]
