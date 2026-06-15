"""E6 — 查询与追踪端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session
from app.repositories.query_repo import QueryTraceRepository
from app.schemas.query import (
    QueryTraceResponse,
    QueryTraceListResponse,
    QueryMetricsResponse,
)
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("/search")
async def search(
    query: str,
    search_mode: str = Query("hybrid"),
    top_k: int = Query(10, ge=1, le=50),
    rerank: bool = True,
    collection: str | None = None,
    category: str | None = None,
    language: str | None = None,
):
    """执行知识库检索查询。"""
    # TODO(E6): 连接 QueryPipeline 实现真实检索
    logger.info(
        "api_search",
        message="API 检索请求",
        metadata={"query": query, "search_mode": search_mode, "top_k": top_k},
    )
    return {
        "query": query,
        "results": [],
        "total": 0,
        "trace_id": "",
        "latency_ms": 0.0,
    }


@router.get("/traces", response_model=QueryTraceListResponse)
async def list_query_traces(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Query 追踪记录（来自 query_traces 表）。"""
    repo = QueryTraceRepository(kb_session)
    rows, total = await repo.paginate(page=page, page_size=page_size)
    items = []
    for r in rows:
        items.append(QueryTraceResponse(
            trace_id=str(r.trace_id),
            user_query=r.user_query,
            collection=r.collection,
            category=r.category,
            language=r.language,
            total_latency_ms=r.total_latency_ms,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            cache_hit=r.cache_hit,
            rejected=r.rejected,
            rejection_reason=r.rejection_reason,
            compliance_score=r.compliance_score,
            stages=r.stages if r.stages else {},
            top_k_results=r.top_k_results if r.top_k_results else [],
            error=r.error,
            created_at=r.created_at.isoformat() if r.created_at else None,
        ).model_dump())
    return QueryTraceListResponse(items=items, total=total, page=page, page_size=page_size)



@router.get("/traces/metrics", response_model=QueryMetricsResponse)
async def get_query_metrics(
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取查询性能指标（p50/p95 延迟、令牌使用、缓存命中率等）。

    从 query_traces 表聚合最近 24 小时的指标。
    """
    repo = QueryTraceRepository(kb_session)
    metrics = await repo.get_metrics_24h()
    return QueryMetricsResponse(**metrics)


@router.get("/traces/{trace_id}")
async def get_query_trace(
    trace_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取单条 Query 追踪详情。"""
    repo = QueryTraceRepository(kb_session)
    r = await repo.find_by_trace_id(trace_id)
    if not r:
        raise HTTPException(status_code=404, detail="追踪记录不存在")

    return QueryTraceResponse(
        trace_id=str(r.trace_id),
        user_query=r.user_query,
        collection=r.collection,
        category=r.category,
        language=r.language,
        total_latency_ms=r.total_latency_ms,
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        total_tokens=r.total_tokens,
        cache_hit=r.cache_hit,
        rejected=r.rejected,
        rejection_reason=r.rejection_reason,
        compliance_score=r.compliance_score,
        stages=r.stages if r.stages else {},
        top_k_results=r.top_k_results if r.top_k_results else [],
        error=r.error,
        created_at=r.created_at.isoformat() if r.created_at else None,
    ).model_dump()

__all__ = ["router"]
