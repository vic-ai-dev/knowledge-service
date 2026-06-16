"""E6 — 查询与追踪端点。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database_sa import get_kb_session
from app.repositories.query_repo import QueryTraceRepository
from app.model.dto.query import (
    QueryTraceResponse,
    QueryTraceListResponse,
    QueryMetricsResponse,
)
from app.common.log import get_logger
from app.common.enums import SearchMode
from app.query_engine import QueryPipeline

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("/search")
async def search(
    kb_session: AsyncSession = Depends(get_kb_session),
    body: dict = Body(...),
):
    """执行知识库检索查询。
    
    支持两种检索模式:
      - vector_only: 仅向量检索
      - hybrid: 向量 + BM25 + RRF 融合 + 可选 Rerank
    """
    query_text = body.get("query", "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query 不能为空")
    
    search_mode = body.get("search_mode", SearchMode.HYBRID.value)
    top_k = body.get("top_k", 10)
    rerank = body.get("rerank", True)
    
    pipeline = QueryPipeline()
    result = await pipeline.execute(
        query_text=query_text,
        search_mode=search_mode,
        top_k=top_k,
        rerank=rerank,
        kb_session=kb_session,
    )
    
    logger.info(
        "api_search",
        message="API 检索请求",
        metadata={
            "query": query_text,
            "search_mode": search_mode,
            "results": len(result.results),
            "latency_ms": result.total_latency_ms,
        },
    )
    return {
        "query": result.query,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "score": r.score,
                "title": r.title,
                "metadata": r.metadata,
            }
            for r in result.results
        ],
        "trace_id": result.trace_id,
        "total_latency_ms": result.total_latency_ms,
        "answer": result.answer,
        "citations": result.citations,
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
            search_mode=r.search_mode,
            rerank=r.rerank,
           category=r.category,
            language=r.language,
            total_latency_ms=r.total_latency_ms,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            cache_hit=r.cache_hit,
            rejected=r.rejected,
            rejection_reason=r.rejection_reason,
            context_precision=r.context_precision,
            context_recall=r.context_recall,
            faithfulness=r.faithfulness,
            answer_relevancy=r.answer_relevancy,
            stages=r.stages if r.stages else {},
            top_k_results=r.top_k_results if r.top_k_results else [],
            results=r.results if r.results else None,
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
        category=r.category,
        language=r.language,
        total_latency_ms=r.total_latency_ms,
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        total_tokens=r.total_tokens,
        cache_hit=r.cache_hit,
        rejected=r.rejected,
        rejection_reason=r.rejection_reason,
        context_precision=r.context_precision,
        context_recall=r.context_recall,
        faithfulness=r.faithfulness,
        answer_relevancy=r.answer_relevancy,
        stages=r.stages if r.stages else {},
        top_k_results=r.top_k_results if r.top_k_results else [],
        results=r.results if r.results else None,
        error=r.error,
        created_at=r.created_at.isoformat() if r.created_at else None,
    ).model_dump()

__all__ = ["router"]
