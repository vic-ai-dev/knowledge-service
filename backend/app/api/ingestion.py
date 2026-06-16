"""E5 — Ingestion 管理端点（含文件校验、上传、历史记录、追踪）。"""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.core.database_sa import get_kb_session
from app.repositories.ingestion_repo import IngestionHistoryRepository, IngestionTraceRepository
from app.repositories.document_repo import DocumentRepository
from app.ingestion.models import IngestionDocument
from app.ingestion.pipeline import IngestionPipeline
from app.common.log import get_logger
from app.common.enums import CATEGORY_VALUES, LANGUAGE_VALUES, IngestionStatus
from app.schemas.ingestion import IngestionHistoryListResponse, IngestionTraceListResponse
import tempfile

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


def _doc_type_from_ext(ext: str) -> str:
    """从文件扩展名推断 doc_type。"""
    mapping = {".md": "md", ".html": "html", ".htm": "html", ".pdf": "pdf"}
    return mapping.get(ext.lower(), "md")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(""),
    language: str = Form(""),
):
    """上传文档文件。

    支持 PDF / Markdown / HTML。异步触发 Ingestion Pipeline。
    文件校验通过后调用 IngestionPipeline 处理。
    """
    _check_rate_limit()
    content = await file.read()
    info = _validate_file(file.filename or "unknown", content)

    # 校验 category / language
    _VALID_CATEGORIES = CATEGORY_VALUES
    _VALID_LANGUAGES = LANGUAGE_VALUES
    if category not in _VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"无效的 category: {category}. 允许值: {_VALID_CATEGORIES}")
    if language not in _VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"无效的 language: {language}. 允许值: {_VALID_LANGUAGES}")

    logger.info(
        "file_uploaded",
        message="文件上传成功",
        metadata={
            "filename": file.filename,
            "size": info["size"],
            "type": info["extension"],
            "sha256": info["sha256"],
            "category": category,
            "language": language,
        },
    )

    # ── 保存上传文件到临时目录 ─────────────────────────
    ext = Path(file.filename or "unknown").suffix
    tmp_dir = Path(tempfile.mkdtemp(prefix="ks_upload_"))
    tmp_path = tmp_dir / f"{info['sha256'][:16]}{ext}"
    try:
        tmp_path.write_bytes(content)
    except Exception as e:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error("upload_save_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    # ── 构建 IngestionDocument ─────────────────────────
    doc_type = _doc_type_from_ext(ext)
    title = Path(file.filename or "untitled").stem

    ingestion_doc = IngestionDocument(
        source_path=str(tmp_path),
        doc_type=doc_type,
        category=category,
        language=language,
        title=title,
        file_size=info["size"],
        file_hash=info["sha256"],
    )

    # ── 创建 IngestionPipeline ─────────────────────────
    pipeline = IngestionPipeline(
        batch_processor=None,
        vector_upserter=None,
        integrity_checker=None,
        progress_callback=None,
    )

    # ── 执行管线 ───────────────────────────────────────
    run_start = time.monotonic()

    try:
        result = await pipeline.process_document(ingestion_doc, force=False)
    except Exception as e:
        elapsed = (time.monotonic() - run_start) * 1000
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(
            "upload_pipeline_error",
            error=str(e),
            metadata={
                "filename": file.filename,
                "elapsed_ms": round(elapsed, 2),
            },
        )
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── 处理结果 ───────────────────────────────────────
    from app.observability.telemetry import current_trace_uuid
    trace_id = str(current_trace_uuid() or uuid.uuid4())

    if result.status.value == IngestionStatus.COMPLETED.value:
        status_msg = "completed"
    elif result.status.value == IngestionStatus.SKIPPED.value:
        status_msg = "skipped (already ingested)"
    else:
        status_msg = "failed"

    stage_details = [
        {"stage": s.stage, "duration_ms": round(s.duration_ms, 2), "items": s.items_processed}
        for s in result.stages
    ]

    return JSONResponse(
        status_code=200 if result.status.value in ("completed", "skipped") else 500,
        content={
            "task_id": result.run_id,
            "trace_id": trace_id,
            "filename": file.filename,
            "size": info["size"],
            "status": status_msg,
            "total_chunks": result.total_chunks,
            "errors": result.errors,
            "stages": stage_details,
            "elapsed_ms": round((time.monotonic() - run_start) * 1000, 2),
            "message": "文件处理完成" if result.status.value == IngestionStatus.COMPLETED.value else f"文件处理失败: {result.errors}",
        },
    )


@router.get("/history")
async def list_ingestion_history(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Ingestion 历史记录（来自 ingestion_history 表）。"""
    repo = IngestionHistoryRepository(kb_session)
    rows, total = await repo.paginate(page=page, page_size=page_size)
    items = []
    for r in rows:
        items.append({
            "id": str(r.id),
            "file_hash": r.file_hash,
            "file_path": r.source_path,
            "file_size": r.file_size,
            "status": r.status,
            "category": r.category,
            "language": r.language,
            "doc_type": r.doc_type,
            "chunk_count": r.total_chunks,
            "error_msg": r.error_message,
            "processed_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/traces")
async def list_ingestion_traces(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Ingestion 追踪记录（来自 ingestion_traces 表）。"""
    repo = IngestionTraceRepository(kb_session)
    rows, total = await repo.paginate(page=page, page_size=page_size)
    items = []
    for r in rows:
        items.append({
            "trace_id": str(r.trace_id),
            "source_path": r.source_path,
            "total_latency_ms": r.total_latency_ms,
            "status": r.status,
            "total_chunks": r.total_chunks,
            "total_images": r.total_images,
            "stages": r.stages if r.stages else {},
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/traces/{trace_id}")
async def get_ingestion_trace(
    trace_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取单条 Ingestion 追踪详情。"""
    repo = IngestionTraceRepository(kb_session)
    r = await repo.find_by_trace_id(trace_id)
    if not r:
        raise HTTPException(status_code=404, detail="追踪记录不存在")

    return {
        "trace_id": str(r.trace_id),
        "source_path": r.source_path,
        "total_latency_ms": r.total_latency_ms,
        "status": r.status,
        "total_chunks": r.total_chunks,
        "total_images": r.total_images,
        "stages": r.stages if r.stages else {},
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
   
@router.get("/status/{run_id}")
async def get_ingestion_status(
    run_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取 Ingestion 运行状态（与 traces/{trace_id} 同源）。"""
    return await get_ingestion_trace(run_id, kb_session)


__all__ = ["router"]
