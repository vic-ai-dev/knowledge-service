"""E5 — Ingestion 管理端点（含文件校验、上传、历史记录、追踪）。"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from asyncpg import Connection

from app.core.settings import get_settings
from app.core.database import get_kb_conn
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# ── 速率限制（简易内存实现，单实例） ─────────────────
_upload_timestamps: list[float] = []
_MAX_UPLOADS_PER_MINUTE = 10


def _check_rate_limit() -> None:
    """检查上传速率限制。"""
    global _upload_timestamps
    now = time.monotonic()
    cutoff = now - 60.0
    _upload_timestamps = [t for t in _upload_timestamps if t > cutoff]
    if len(_upload_timestamps) >= _MAX_UPLOADS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="上传过于频繁，请稍后再试")
    _upload_timestamps.append(now)


_ALLOWED_EXTENSIONS = {".pdf", ".md", ".html"}


def _validate_file(filename: str, content: bytes) -> dict:
    """校验文件类型和大小。"""
    settings = get_settings()
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS and ext.lstrip(".") not in settings.server.allowed_extensions:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    if len(content) > settings.server.max_file_size:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({settings.server.max_file_size / 1024 / 1024:.0f}MB)")

    sha256 = hashlib.sha256(content).hexdigest()
    return {"extension": ext.lstrip("."), "sha256": sha256, "size": len(content)}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection: str = "default",
    category: str = "",
    language: str = "",
):
    """上传文档文件。

    支持 PDF / Markdown / HTML。异步触发 Ingestion Pipeline。
    文件校验通过后返回任务 ID。
    """
    _check_rate_limit()
    content = await file.read()
    info = _validate_file(file.filename or "unknown", content)

    # TODO(E5): 提交到 Ingestion Pipeline 异步处理
    logger.info(
        "file_uploaded",
        message="文件上传成功",
        metadata={
            "filename": file.filename,
            "size": info["size"],
            "type": info["extension"],
            "sha256": info["sha256"],
            "collection": collection,
            "category": category,
            "language": language,
        },
    )

    return JSONResponse(
        status_code=202,
        content={
            "task_id": "pending",
            "filename": file.filename,
            "size": info["size"],
            "status": "pending",
            "message": "文件已接收，正在排队处理",
        },
    )


@router.get("/history")
async def list_ingestion_history(
    kb_conn: Connection = Depends(get_kb_conn),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Ingestion 历史记录（来自 ingestion_history 表）。"""
    offset = (page - 1) * page_size

    count_row = await kb_conn.fetchrow("SELECT COUNT(*)::int AS cnt FROM ingestion_history")
    total = count_row["cnt"] if count_row else 0

    rows = await kb_conn.fetch("""
        SELECT id, file_hash, file_path, file_size, status, category, language,
               doc_type, chunk_count, error_msg, processed_at
        FROM ingestion_history
       ORDER BY processed_at DESC
        LIMIT $1 OFFSET $2
   """, page_size, offset)

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "file_hash": r["file_hash"],
            "file_path": r["file_path"],
            "file_size": r["file_size"],
            "status": r["status"],
            "category": r["category"],
            "language": r["language"],
            "doc_type": r["doc_type"],
            "chunk_count": r["chunk_count"],
            "error_msg": r["error_msg"],
            "processed_at": r["processed_at"].isoformat() if r["processed_at"] else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/traces")
async def list_ingestion_traces(
    kb_conn: Connection = Depends(get_kb_conn),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Ingestion 追踪记录（来自 ingestion_traces 表）。"""
    offset = (page - 1) * page_size

    count_row = await kb_conn.fetchrow("SELECT COUNT(*)::int AS cnt FROM ingestion_traces")
    total = count_row["cnt"] if count_row else 0

    rows = await kb_conn.fetch("""
        SELECT trace_id, source_path, collection, total_latency_ms, status,
               total_chunks, total_images, stages, error, created_at
        FROM ingestion_traces
       ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
   """, page_size, offset)

    items = []
    for r in rows:
        items.append({
            "trace_id": str(r["trace_id"]),
            "source_path": r["source_path"],
            "collection": r["collection"],
            "total_latency_ms": r["total_latency_ms"],
            "status": r["status"],
            "total_chunks": r["total_chunks"],
            "total_images": r["total_images"],
            "stages": r["stages"] if r["stages"] else {},
            "error": r["error"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/traces/{trace_id}")
async def get_ingestion_trace(
    trace_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
):
    """获取单条 Ingestion 追踪详情。"""
    row = await kb_conn.fetchrow("""
        SELECT trace_id, source_path, collection, total_latency_ms, status,
               total_chunks, total_images, stages, error, created_at
        FROM ingestion_traces
        WHERE trace_id = $1::uuid
    """, trace_id)
    if not row:
        raise HTTPException(status_code=404, detail="追踪记录不存在")

    return {
        "trace_id": str(row["trace_id"]),
        "source_path": row["source_path"],
        "collection": row["collection"],
        "total_latency_ms": row["total_latency_ms"],
        "status": row["status"],
        "total_chunks": row["total_chunks"],
        "total_images": row["total_images"],
        "stages": row["stages"] if row["stages"] else {},
        "error": row["error"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
@router.get("/status/{run_id}")
async def get_ingestion_status(
    run_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
):
    """获取 Ingestion 运行状态（与 traces/{trace_id} 同源）。"""
    return await get_ingestion_trace(run_id, kb_conn)


__all__ = ["router"]
