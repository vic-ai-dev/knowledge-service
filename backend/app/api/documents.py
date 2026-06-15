"""E12 — 文档管理 API（文档 CRUD、批量删除、重新索引、集合管理、文档统计）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg import Connection

from app.core.database import get_kb_conn, get_rag_conn
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    kb_conn: Connection = Depends(get_kb_conn),
    collection: str | None = Query(None),
    category: str | None = Query(None),
    language: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """文档中心 — 文档库列表。"""
    where_clauses = ["d.is_deleted = FALSE"]
    params = []
    idx = 1

    if collection:
        where_clauses.append(f"d.collection = ${idx}")
        params.append(collection)
        idx += 1
    if category:
        where_clauses.append(f"d.category = ${idx}")
        params.append(category)
        idx += 1
    if language:
        where_clauses.append(f"d.language = ${idx}")
        params.append(language)
        idx += 1

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size

    count_row = await kb_conn.fetchrow(f"SELECT COUNT(*)::int AS cnt FROM documents d WHERE {where_sql}", *params)
    total = count_row["cnt"] if count_row else 0

    params.extend([page_size, offset])
    rows = await kb_conn.fetch(f"""
        SELECT d.id, d.source_path, d.title, d.collection, d.category, d.language,
               d.doc_type, d.file_size, d.file_hash, d.chunk_count, d.image_count,
               d.ingested_at, d.updated_at, d.is_deleted
        FROM documents d
        WHERE {where_sql}
        ORDER BY d.ingested_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)

    items = []
    for r in rows:
        items.append({
            "id": str(r["id"]),
            "source_path": r["source_path"],
            "title": r["title"],
            "collection": r["collection"],
            "category": r["category"],
            "language": r["language"],
            "doc_type": r["doc_type"],
            "file_size": r["file_size"],
            "chunk_count": r["chunk_count"],
            "ingested_at": r["ingested_at"].isoformat() if r["ingested_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "is_deleted": r["is_deleted"],
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
    rag_conn: Connection = Depends(get_rag_conn),
):
    """获取单个文档详情。"""
    row = await kb_conn.fetchrow("""
        SELECT d.id, d.source_path, d.title, d.collection, d.category, d.language,
               d.doc_type, d.file_size, d.file_hash, d.chunk_count, d.image_count,
               d.ingested_at, d.updated_at, d.is_deleted
        FROM documents d
        WHERE d.id = $1::uuid AND d.is_deleted = FALSE
    """, doc_id)

    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": str(row["id"]),
        "source_path": row["source_path"],
        "title": row["title"],
        "collection": row["collection"],
        "category": row["category"],
        "language": row["language"],
        "doc_type": row["doc_type"],
        "file_size": row["file_size"],
        "chunk_count": row["chunk_count"],
        "ingested_at": row["ingested_at"].isoformat() if row["ingested_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "is_deleted": row["is_deleted"],
    }


@router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    rag_conn: Connection = Depends(get_rag_conn),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取指定文档的分块列表。"""
    offset = (page - 1) * page_size

    count_row = await rag_conn.fetchrow(
        "SELECT COUNT(*)::int AS cnt FROM document_chunks WHERE doc_id = $1::uuid", doc_id
    )
    total = count_row["cnt"] if count_row else 0

    rows = await rag_conn.fetch("""
        SELECT c.id, c.doc_id, c.chunk_index, c.text, c.metadata, c.source_path,
               c.token_count, c.created_at
        FROM document_chunks c
        WHERE c.doc_id = $1::uuid
        ORDER BY c.chunk_index ASC
        LIMIT $2 OFFSET $3
    """, doc_id, page_size, offset)

    items = []
    for r in rows:
        items.append({
            "id": str(r["id"]),
            "doc_id": str(r["doc_id"]) if r["doc_id"] else None,
            "chunk_index": r["chunk_index"],
            "text": r["text"],
            "metadata": r["metadata"] if r["metadata"] else {},
            "source_path": r["source_path"],
            "token_count": r["token_count"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/{doc_id}")
async def update_document(
    doc_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
    title: str | None = None,
    category: str | None = None,
    language: str | None = None,
    collection: str | None = None,
):
    """更新文档 metadata。"""
    updates = []
    params = []
    idx = 1

    if title is not None:
        updates.append(f"title = ${idx}")
        params.append(title)
        idx += 1
    if category is not None:
        updates.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if language is not None:
        updates.append(f"language = ${idx}")
        params.append(language)
        idx += 1
    if collection is not None:
        updates.append(f"collection = ${idx}")
        params.append(collection)
        idx += 1

    if updates:
        updates.append("updated_at = NOW()")
        params.append(doc_id)
        set_clause = ", ".join(updates)
        await kb_conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ${idx}::uuid", *params)

    logger.info(
        "document_updated",
        event_type="http_request",
        message="文档已更新",
        metadata={"doc_id": doc_id, "title": title, "category": category, "language": language},
    )
    return {"status": "updated", "doc_id": doc_id}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
    rag_conn: Connection = Depends(get_rag_conn),
):
    """删除单个文档（同时删除向量和 BM25 索引）。"""
    # 软删除文档
    result = await kb_conn.execute(
        "UPDATE documents SET is_deleted = TRUE, updated_at = NOW() WHERE id = $1::uuid AND is_deleted = FALSE",
        doc_id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="文档不存在或已删除")

    # 删除对应 chunks
    await rag_conn.execute("DELETE FROM document_chunks WHERE doc_id = $1::uuid", doc_id)

    logger.info(
        "document_deleted",
        event_type="http_request",
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
        event_type="http_request",
        message="文档重新索引已触发",
        metadata={"doc_id": doc_id},
    )
    return {"status": "reindexing", "doc_id": doc_id}


@router.post("/batch-delete")
async def batch_delete_documents(
    body: dict,
    kb_conn: Connection = Depends(get_kb_conn),
    rag_conn: Connection = Depends(get_rag_conn),
):
    """批量删除文档。"""
    doc_ids = body.get("ids", [])
    if not doc_ids:
        raise HTTPException(status_code=400, detail="请提供要删除的文档 ID 列表")

    # 批量软删除
    placeholders = ", ".join(f"${i}::uuid" for i in range(1, len(doc_ids) + 1))
    await kb_conn.execute(
        f"UPDATE documents SET is_deleted = TRUE, updated_at = NOW() WHERE id IN ({placeholders}) AND is_deleted = FALSE",
        *doc_ids,
    )
    # 批量删除 chunks
    await rag_conn.execute(
        f"DELETE FROM document_chunks WHERE doc_id IN ({placeholders})",
        *doc_ids,
    )

    logger.info(
        "documents_batch_deleted",
        event_type="http_request",
        message="批量删除文档",
        metadata={"count": len(doc_ids)},
    )
    return {"status": "deleted", "doc_ids": doc_ids, "count": len(doc_ids)}


@router.get("/stats")
async def get_document_stats(
    kb_conn: Connection = Depends(get_kb_conn),
    rag_conn: Connection = Depends(get_rag_conn),
):
    """文档统计概览。"""
    row = await kb_conn.fetchrow("""
        SELECT
            COUNT(*)::int AS total_documents,
            COALESCE(SUM(file_size), 0)::bigint AS total_size_bytes
        FROM documents
        WHERE is_deleted = FALSE
    """)
    total_documents = row["total_documents"] if row else 0
    total_size_bytes = row["total_size_bytes"] if row else 0

    chunk_row = await rag_conn.fetchrow("SELECT COUNT(*)::int AS total_chunks FROM document_chunks")
    total_chunks = chunk_row["total_chunks"] if chunk_row else 0

    cat_rows = await kb_conn.fetch("""
        SELECT category, COUNT(*)::int AS cnt
        FROM documents WHERE is_deleted = FALSE GROUP BY category
    """)
    by_category = {r["category"]: r["cnt"] for r in cat_rows}

    lang_rows = await kb_conn.fetch("""
        SELECT language, COUNT(*)::int AS cnt
        FROM documents WHERE is_deleted = FALSE GROUP BY language
    """)
    by_language = {r["language"]: r["cnt"] for r in lang_rows}

    type_rows = await kb_conn.fetch("""
        SELECT doc_type, COUNT(*)::int AS cnt
        FROM documents WHERE is_deleted = FALSE GROUP BY doc_type
    """)
    by_type = {r["doc_type"]: r["cnt"] for r in type_rows}

    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "by_category": by_category,
        "by_language": by_language,
        "by_type": by_type,
        "total_size_bytes": total_size_bytes,
    }


__all__ = ["router"]
