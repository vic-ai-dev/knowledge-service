"""QueryTraceRepository — 查询追踪 CRUD。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.model.entity.query import QueryTrace
from app.repositories.base import BaseRepository


class QueryTraceRepository(BaseRepository[QueryTrace]):
    model_cls = QueryTrace

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_by_trace_id(
        self, trace_id: str | uuid.UUID
    ) -> QueryTrace | None:
        if isinstance(trace_id, str):
            trace_id = uuid.UUID(trace_id)
        stmt = select(QueryTrace).where(QueryTrace.trace_id == trace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[QueryTrace], int]:
        total = await self.count()
        offset = (page - 1) * page_size
        rows = await self.find_all(
            order_by=QueryTrace.created_at.desc(),
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def get_metrics_24h(self) -> dict:
        """获取最近 24 小时的查询性能指标。"""
        # 使用 raw SQL 来支持 PERCENTILE_CONT
        stmt = text("""
            SELECT
                COUNT(*)::int AS total_queries,
                COALESCE(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_latency_ms), 0)::float AS p50_latency_ms,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_latency_ms), 0)::float AS p95_latency_ms,
                COALESCE(SUM(input_tokens), 0)::bigint AS total_input_tokens,
                COALESCE(SUM(output_tokens), 0)::bigint AS total_output_tokens,
                COALESCE(AVG(CASE WHEN cache_hit THEN 1.0 ELSE 0.0 END), 0)::float AS cache_hit_rate,
                COALESCE(AVG(CASE WHEN rejected THEN 1.0 ELSE 0.0 END), 0)::float AS rejection_rate,
                COALESCE(AVG(context_precision), 0)::float AS avg_context_precision,
                COALESCE(AVG(context_recall), 0)::float AS avg_context_recall,
                COALESCE(AVG(faithfulness), 0)::float AS avg_faithfulness,
                COALESCE(AVG(answer_relevancy), 0)::float AS avg_answer_relevancy
            FROM query_traces
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return {
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_queries": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "cache_hit_rate": 0.0,
                "rejection_rate": 0.0,
                "avg_context_precision": 0.0,
                "avg_context_recall": 0.0,
                "avg_faithfulness": 0.0,
                "avg_answer_relevancy": 0.0,
            }

        return {
            "p50_latency_ms": row.p50_latency_ms,
            "p95_latency_ms": row.p95_latency_ms,
            "total_queries": row.total_queries,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "cache_hit_rate": row.cache_hit_rate,
            "rejection_rate": row.rejection_rate,
            "avg_context_precision": row.avg_context_precision,
            "avg_context_recall": row.avg_context_recall,
            "avg_faithfulness": row.avg_faithfulness,
            "avg_answer_relevancy": row.avg_answer_relevancy,
        }


__all__ = ["QueryTraceRepository"]
