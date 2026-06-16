"""E7 — 评估端点。

实现 GoldenTestSet CRUD + 评估运行 + 结果查询。
"""

from __future__ import annotations

import uuid
import json
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete
from pydantic import BaseModel

from app.core.database_sa import get_kb_session
from app.repositories.base import BaseRepository
from app.models.evaluation import EvaluationResult, GoldenTestSet
from app.schemas.evaluation import (
    EvaluationResultResponse,
    EvaluationResultListResponse,
    GoldenTestSetResponse,
    GoldenTestSetListResponse,
    EvalRunRequest,
    EvalRunResponse,
)
from app.libs.evaluator.runner import EvalRunner
from app.common.log import get_logger
from app.common.enums import EvaluationRunStatus

logger = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])

# ── Forward ─────────────────────────────────────────────

class EvalResultRepo(BaseRepository[EvaluationResult]):
    pass

class TestSetRepo(BaseRepository[GoldenTestSet]):
    pass


@router.get("/testsets", response_model=GoldenTestSetListResponse)
async def list_test_sets(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出所有 Golden Test Set。"""
    repo = TestSetRepo(kb_session)
    stmt = select(GoldenTestSet).order_by(GoldenTestSet.created_at.desc())
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = await kb_session.execute(stmt)
    rows = list(result.scalars().all())

    count_stmt = select(func.count()).select_from(GoldenTestSet)
    total_result = await kb_session.execute(count_stmt)
    total = total_result.scalar() or 0

    return GoldenTestSetListResponse(
        items=[GoldenTestSetResponse(
            id=str(r.id),
            name=r.name,
            queries=r.queries,
            category=r.category,
            language=r.language,
            description=r.description,
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        ) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


class TestSetCreateRequest(BaseModel):
    name: str
    queries: list[dict]
    category: str | None = None
    language: str | None = None
    description: str | None = None


@router.post("/testsets")
async def create_test_set(
    body: TestSetCreateRequest,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """创建新的 Golden Test Set。"""
    test_set = GoldenTestSet(
        name=body.name,
        queries=body.queries,
        category=body.category,
        language=body.language,
        description=body.description,
    )
    kb_session.add(test_set)
    await kb_session.flush()
    await kb_session.commit()
    return {"id": str(test_set.id), "status": "created"}


@router.delete("/testsets/{test_set_id}")
async def delete_test_set(
    test_set_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """删除 Golden Test Set。"""
    try:
        ts_id = uuid.UUID(test_set_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid test_set_id")
    stmt = select(GoldenTestSet).where(GoldenTestSet.id == ts_id)
    result = await kb_session.execute(stmt)
    ts = result.scalar_one_or_none()
    if ts is None:
        raise HTTPException(status_code=404, detail="TestSet not found")
    await kb_session.delete(ts)
    await kb_session.commit()
    return {"status": "deleted"}


@router.post("/run", response_model=EvalRunResponse)
async def run_evaluation(
    body: EvalRunRequest,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """运行评估任务。"""
    task_id = str(uuid.uuid4())
    runner = EvalRunner(kb_session)

    try:
        if body.test_set_id:
            results = await runner.run_test_set(
                test_set_id=body.test_set_id,
                search_mode=body.search_mode,
                top_k=body.top_k,
                rerank=body.rerank,
            )
            logger.info("eval_run_complete", metadata={
                "task_id": task_id,
                "test_set_id": body.test_set_id,
                "completed": len(results),
            })
            return EvalRunResponse(
                task_id=task_id,
                status=EvaluationRunStatus.COMPLETED.value,
                completed=len(results),
                total=len(results),
            )
        else:
            # 运行所有测试集
            stmt = select(GoldenTestSet)
            result = await kb_session.execute(stmt)
            all_sets = list(result.scalars().all())
            total_completed = 0
            total_queries = 0
            for ts in all_sets:
                try:
                    results = await runner.run_test_set(
                        test_set_id=str(ts.id),
                        search_mode=body.search_mode,
                        top_k=body.top_k,
                        rerank=body.rerank,
                    )
                    total_completed += len(results)
                    total_queries += len(ts.queries)
                except Exception as e:
                    logger.error("eval_run_failed", error=str(e), metadata={"test_set": ts.name})
            return EvalRunResponse(
                task_id=task_id,
                status=EvaluationRunStatus.COMPLETED.value,
                completed=total_completed,
                total=total_queries,
            )
    except Exception as e:
        logger.error("eval_run_error", error=str(e))
        return EvalRunResponse(
            task_id=task_id,
            status=EvaluationRunStatus.ERROR.value,
            error=str(e),
        )


@router.get("/results", response_model=EvaluationResultListResponse)
async def list_evaluation_results(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出评估结果。"""
    repo = EvalResultRepo(kb_session)
    stmt = select(EvaluationResult).order_by(EvaluationResult.created_at.desc())
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = await kb_session.execute(stmt)
    rows = list(result.scalars().all())

    count_stmt = select(func.count()).select_from(EvaluationResult)
    total_result = await kb_session.execute(count_stmt)
    total = total_result.scalar() or 0

    return EvaluationResultListResponse(
        items=[EvaluationResultResponse(
            id=str(r.id),
            metrics=r.metrics,
            test_set=r.test_set,
            backends_used=[
                f"search_mode={r.backends_used.get('search_mode', '?')}",
                "rerank" if r.backends_used.get("rerank") else "no-rerank",
            ] if r.backends_used else None,
            created_at=r.created_at.isoformat() if r.created_at else None,
        ) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


__all__ = ["router"]
