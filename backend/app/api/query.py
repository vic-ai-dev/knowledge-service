"""E6 — 查询与追踪端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg import Connection

from app.core.database import get_kb_conn
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
        event_type="retrieval",
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


@router.get("/traces")
async def list_query_traces(
    kb_conn: Connection = Depends(get_kb_conn),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Query 追踪记录（来自 query_traces 表）。"""
    offset = (page - 1) * page_size

    count_row = await kb_conn.fetchrow("SELECT COUNT(*)::int AS cnt FROM query_traces")
    total = count_row["cnt"] if count_row else 0

    rows = await kb_conn.fetch("""
        SELECT trace_id, user_query, collection, category, language,
               total_latency_ms, input_tokens, output_tokens, total_tokens,
               cache_hit, rejected, rejection_reason, compliance_score,
               stages, top_k_results, error, created_at
        FROM query_traces
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """, page_size, offset)

    items = []
    for r in rows:
        items.append({
            "trace_id": str(r["trace_id"]),
            "user_query": r["user_query"],
            "collection": r["collection"],
            "category": r["category"],
            "language": r["language"],
            "total_latency_ms": r["total_latency_ms"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "total_tokens": r["total_tokens"],
            "cache_hit": r["cache_hit"],
            "rejected": r["rejected"],
            "rejection_reason": r["rejection_reason"],
            "compliance_score": r["compliance_score"],
            "stages": r["stages"] if r["stages"] else {},
            "top_k_results": r["top_k_results"] if r["top_k_results"] else [],
            "error": r["error"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}



@router.get("/traces/metrics")
async def get_query_metrics(
    kb_conn: Connection = Depends(get_kb_conn),
):
    """获取查询性能指标（p50/p95 延迟、令牌使用、缓存命中率等）。

    从 query_traces 表聚合最近 24 小时的指标。
    """
    row = await kb_conn.fetchrow("""
        SELECT
            COUNT(*)::int AS total_queries,
            COALESCE(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_latency_ms), 0)::float AS p50_latency_ms,
            COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_latency_ms), 0)::float AS p95_latency_ms,
            COALESCE(SUM(input_tokens), 0)::bigint AS total_input_tokens,
            COALESCE(SUM(output_tokens), 0)::bigint AS total_output_tokens,
            COALESCE(AVG(CASE WHEN cache_hit THEN 1.0 ELSE 0.0 END), 0)::float AS cache_hit_rate,
            COALESCE(AVG(CASE WHEN rejected THEN 1.0 ELSE 0.0 END), 0)::float AS rejection_rate,
            COALESCE(AVG(compliance_score), 0)::float AS avg_compliance_score
        FROM query_traces
        WHERE created_at > NOW() - INTERVAL '24 hours'
    """)

    if not row:
        return {
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "total_queries": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hit_rate": 0.0,
            "rejection_rate": 0.0,
            "avg_compliance_score": 0.0,
        }

    return {
        "p50_latency_ms": row["p50_latency_ms"],
        "p95_latency_ms": row["p95_latency_ms"],
        "total_queries": row["total_queries"],
        "total_input_tokens": row["total_input_tokens"],
        "total_output_tokens": row["total_output_tokens"],
        "cache_hit_rate": row["cache_hit_rate"],
        "rejection_rate": row["rejection_rate"],
        "avg_compliance_score": row["avg_compliance_score"],
    }


@router.get("/traces/{trace_id}")
async def get_query_trace(
    trace_id: str,
    kb_conn: Connection = Depends(get_kb_conn),
):
    """获取单条 Query 追踪详情。"""
    row = await kb_conn.fetchrow("""
        SELECT trace_id, user_query, collection, category, language,
               total_latency_ms, input_tokens, output_tokens, total_tokens,
               cache_hit, rejected, rejection_reason, compliance_score,
               stages, top_k_results, error, created_at
        FROM query_traces
        WHERE trace_id = $1::uuid
    """, trace_id)

    if not row:
        raise HTTPException(status_code=404, detail="追踪记录不存在")

    return {
        "trace_id": str(row["trace_id"]),
        "user_query": row["user_query"],
        "collection": row["collection"],
        "category": row["category"],
        "language": row["language"],
        "total_latency_ms": row["total_latency_ms"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "total_tokens": row["total_tokens"],
        "cache_hit": row["cache_hit"],
        "rejected": row["rejected"],
        "rejection_reason": row["rejection_reason"],
        "compliance_score": row["compliance_score"],
        "stages": row["stages"] if row["stages"] else {},
        "top_k_results": row["top_k_results"] if row["top_k_results"] else [],
        "error": row["error"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }

__all__ = ["router"]
