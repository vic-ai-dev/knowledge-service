"""E12 — 文档管理 API（文档 CRUD、批量删除、重新索引、集合管理、文档统计）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database_sa import get_kb_session, get_rag_session
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import DocumentChunkRepository
from app.repositories.ingestion_repo import IngestionHistoryRepository
from app.model.dto.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    DocumentStatsResponse,
)
from app.model.entity.document import Document
from app.common.log import get_logger
from app.model.dto.document import DocumentResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def _destr(id_val: uuid.UUID) -> str:
    return str(id_val)


def _doc_to_response(doc: Document, status: str | None = None) -> dict:
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
        status=status,
        ingested_at=doc.ingested_at.isoformat() if doc.ingested_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
        is_deleted=doc.is_deleted,
    ).model_dump()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    kb_session: AsyncSession = Depends(get_kb_session),
    category: str | None = Query(None),
    language: str | None = Query(None),
    doc_type: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """文档中心 — 文档库列表。"""
    repo = DocumentRepository(kb_session)
    rows, total = await repo.find_all_active(
       category=category,
       language=language,
       doc_type=doc_type,
       search=search,
       page=page,
       page_size=page_size,
    )
    # 批量查询 ingestion_history 状态
    status_map: dict[str, str | None] = {}
    for d in rows:
        from app.model.entity.ingestion import IngestionHistory
        from sqlalchemy import select
        stmt = (
            select(IngestionHistory)
            .where(IngestionHistory.document_id == d.id)
            .order_by(IngestionHistory.created_at.desc())
            .limit(1)
        )
        result = await kb_session.execute(stmt)
        hist = result.scalar_one_or_none()
        if hist:
            status_map[str(d.id)] = hist.status
    items = [_doc_to_response(d, status_map.get(str(d.id))) for d in rows]
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


@router.get("/{doc_id}/bm25-stats")
async def get_document_bm25_stats(
    doc_id: str,
    rag_session: AsyncSession = Depends(get_rag_session),
):
    """获取指定文档各 Chunk 的 BM25 稀疏编码统计。
 
    返回每个 chunk 的：
      - doc_length: 分词后的总 term 数
      - unique_terms: 不重复的 term 数
    分词策略与 BM25Indexer 一致（jieba + 过滤短词）。
    """
    import asyncio
    import jieba
 
    repo = DocumentChunkRepository(rag_session)
    rows, total = await repo.find_by_document(doc_id, page=1, page_size=100000)
 
    def compute(chunk) -> dict:
        tokens = [w.lower() for w in jieba.lcut(chunk.text) if len(w.strip()) >= 2]
        return {
            "chunk_id": str(chunk.id),
            "doc_length": len(tokens),
            "unique_terms": len(set(tokens)),
        }
 
    items = await asyncio.gather(*[
        asyncio.to_thread(compute, c) for c in rows
    ])
 
    logger.info(
        "document_bm25_stats",
        message="BM25 统计已生成",
        metadata={"doc_id": doc_id, "total": total},
    )
    return {"items": items, "total": total}
 
 
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



@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """级联删除文档：PGVector chunks → BM25 索引 → Ingestion 记录 → 文档。

    三个步骤独立连接，不做分布式事务（先不引入 2PC／Saga）。
    如果中间步骤失败，已清理的内容不会回滚，最坏情况是遗留少量孤立数据。
    """
    # 1. 查找文档
    repo = DocumentRepository(kb_session)
    doc = await repo.find_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    source_path = doc.source_path
    logger.info("delete_processing", metadata={"doc_id": document_id, "source_path": source_path})

    # 2. 删除 PGVector chunks（knowledge_rag 库）
    from app.ingestion.storage.vector_upserter import VectorUpserter
    try:
        vector_upserter = VectorUpserter()
        deleted_chunks = await vector_upserter.delete_by_doc_id(document_id)
    except Exception as e:
        logger.error("delete_vector_failed", error=str(e), metadata={"doc_id": document_id})
        deleted_chunks = 0

    # 3. 删除 BM25 索引（knowledge_rag 库，同一张表）
    from app.ingestion.storage.bm25_indexer import BM25Indexer
    try:
        bm25 = BM25Indexer()
        deleted_bm25 = 1 if await bm25.remove_document(document_id) else 0
    except Exception as e:
        logger.error("delete_bm25_failed", error=str(e), metadata={"doc_id": document_id})
        deleted_bm25 = 0

    # 4. 级联删除知识库记录（IngestionHistory + IngestionTrace + Document）
    deleted_doc = await repo.cascade_delete(document_id)
    await kb_session.commit()

    logger.info("delete_complete", metadata={
        "doc_id": document_id,
        "deleted_chunks": deleted_chunks,
        "deleted_bm25": deleted_bm25,
        "deleted_doc": deleted_doc,
    })

    return {
        "status": "deleted",
        "doc_id": document_id,
        "deleted_chunks": deleted_chunks,
        "deleted_bm25": deleted_bm25,
        "deleted_doc": deleted_doc,
    }


__all__ = ["router"]
