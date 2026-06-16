"""E4 — 数据浏览端点（文档列表、分块浏览）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session, get_rag_session
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import DocumentChunkRepository
from app.models.chunk import DocumentChunk
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/data", tags=["data"])


@router.get("/documents")
async def list_documents(
    kb_session: AsyncSession = Depends(get_kb_session),
    category: str | None = Query(None),
    language: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出知识库文档（分页 + 筛选）。"""
    repo = DocumentRepository(kb_session)
    rows, total = await repo.find_all_active(
        category=category,
        language=language,
        page=page,
        page_size=page_size,
    )
    items = []
    for d in rows:
        items.append({
            "id": str(d.id),
            "source_path": d.source_path,
            "title": d.title,
            "category": d.category,
            "language": d.language,
            "doc_type": d.doc_type,
            "file_size": d.file_size,
            "chunk_count": d.chunk_count,
            "ingested_at": d.ingested_at.isoformat() if d.ingested_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "is_deleted": d.is_deleted,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/chunks")
async def list_chunks(
    rag_session: AsyncSession = Depends(get_rag_session),
    doc_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出文档分块。"""
    repo = DocumentChunkRepository(rag_session)
    if doc_id:
        rows, total = await repo.find_by_document(doc_id, page=page, page_size=page_size)
    else:
        total = await repo.get_total_count()
        offset = (page - 1) * page_size
        rows = await repo.find_all(order_by=DocumentChunk.chunk_index, limit=page_size, offset=offset)

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


@router.get("/categories")
async def list_categories():
    """列出所有分类。"""
    return {
        "categories": [
            {"id": "employee_handbook", "name": "员工手册"},
            {"id": "compliance", "name": "合规指南"},
            {"id": "technical_spec", "name": "技术规范"},
            {"id": "architecture", "name": "架构文档"},
        ]
    }


@router.get("/languages")
async def list_languages():
    """列出所有语言。"""
    return {"languages": [{"id": "zh", "name": "中文"}, {"id": "en", "name": "英文"}]}


@router.get("/chunks/{chunk_id}")
async def get_chunk(
    chunk_id: str,
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """获取单个分块详情。"""
    repo = DocumentChunkRepository(rag_session)
    c = await repo.find_by_id(chunk_id)
    if not c:
        raise HTTPException(status_code=404, detail="Chunk 不存在")

    return {
        "id": str(c.id),
        "doc_id": str(c.doc_id) if c.doc_id else None,
        "chunk_index": c.chunk_index,
        "text": c.text,
        "metadata": c.metadata_ if c.metadata_ else {},
        "source_path": c.source_path,
        "token_count": c.token_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
