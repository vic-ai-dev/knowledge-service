"""E7 — 评估端点。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/testsets")
async def list_test_sets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Golden Test Set。"""
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.post("/run")
async def run_evaluation(testset_id: str):
    """运行评估任务。"""
    return {"task_id": "pending", "status": "queued"}


@router.get("/results")
async def list_evaluation_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出评估结果。"""
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


__all__ = ["router"]
