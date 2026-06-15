"""E4 — 数据浏览端点（文档列表、分块浏览、集合 CRUD）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg import Connection

from app.core.database import get_kb_conn, get_rag_conn
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/data", tags=["data"])


@router.get("/documents")
async def list_documents(
    kb_conn: Connection = Depends(get_kb_conn),
    collection: str = "default",
    category: str | None = Query(None),
    language: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出知识库文档（分页 + 筛选）。"""
    where_clauses = ["d.is_deleted = FALSE"]
    params = []
    idx = 1

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


@router.get("/chunks")
async def list_chunks(
    rag_conn: Connection = Depends(get_rag_conn),
    doc_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出文档分块。"""
    where_clauses = []
    params = []
    idx = 1

    if doc_id:
        where_clauses.append(f"c.doc_id = ${idx}::uuid")
        params.append(doc_id)
        idx += 1

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
    offset = (page - 1) * page_size

    count_row = await rag_conn.fetchrow(f"SELECT COUNT(*)::int AS cnt FROM document_chunks c WHERE {where_sql}", *params)
    total = count_row["cnt"] if count_row else 0

    params.extend([page_size, offset])
    rows = await rag_conn.fetch(f"""
        SELECT c.id, c.doc_id, c.chunk_index, c.text, c.metadata, c.source_path,
               c.token_count, c.created_at
        FROM document_chunks c
        WHERE {where_sql}
        ORDER BY c.chunk_index ASC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)

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


@router.get("/collections")
async def list_collections(
    rag_conn: Connection = Depends(get_rag_conn),
):
    """列出所有集合。"""
    rows = await rag_conn.fetch("""
        SELECT c.id, c.name, c.description, c.document_count, c.chunk_count,
               c.created_at, c.updated_at
        FROM collections c
        ORDER BY c.created_at DESC
    """)
    collections = []
    for r in rows:
        collections.append({
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "document_count": r["document_count"],
            "chunk_count": r["chunk_count"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        })
    return {"collections": collections}


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


__all__ = ["router"]


@router.post("/collections")
async def create_collection(
    body: dict,
    rag_conn: Connection = Depends(get_rag_conn),
):
    """创建新的集合。"""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="集合名称不能为空")

    description = body.get("description", "").strip()
    from uuid import uuid4
    col_id = uuid4()

    await rag_conn.execute(
        "INSERT INTO collections (id, name, description) VALUES ($1::uuid, $2, $3)",
        col_id, name, description,
    )

    logger.info(
        "collection_created",
        message="集合已创建",
        metadata={"name": name, "description": description},
    )
    return {"status": "created", "id": str(col_id), "name": name}


@router.delete("/collections/{name}")
async def delete_collection(
    name: str,
    rag_conn: Connection = Depends(get_rag_conn),
):
    """删除指定集合。"""
    row = await rag_conn.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="集合不存在")

    col_id = row["id"]

    # 删除集合下所有 chunks
    await rag_conn.execute(
        "DELETE FROM document_chunks WHERE doc_id IN (SELECT id FROM documents WHERE collection = $1)",
        name,
    )
    await rag_conn.execute("DELETE FROM collections WHERE id = $1::uuid", col_id)

    logger.info(
        "collection_deleted",
        message="集合已删除",
        metadata={"name": name},
    )
    return {"status": "deleted", "name": name}


@router.get("/chunks/{chunk_id}")
async def get_chunk(
    chunk_id: str,
    rag_conn: Connection = Depends(get_rag_conn),
):
    """获取单个分块详情。"""
    row = await rag_conn.fetchrow(
        "SELECT id, doc_id, chunk_index, text, metadata, source_path, token_count, created_at "
        "FROM document_chunks WHERE id = $1::uuid",
        chunk_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Chunk 不存在")

    return {
        "id": str(row["id"]),
        "doc_id": str(row["doc_id"]) if row["doc_id"] else None,
        "chunk_index": row["chunk_index"],
        "text": row["text"],
        "metadata": row["metadata"] if row["metadata"] else {},
        "source_path": row["source_path"],
        "token_count": row["token_count"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
