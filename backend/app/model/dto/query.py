"""Query Pydantic Schemas。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QueryTraceResponse(BaseModel):
    """查询追踪返回体。"""
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    user_query: str
    category: str | None = None
    language: str | None = None
    search_mode: str | None = None
    rerank: bool | None = None
    total_latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_hit: bool = False
    rejected: bool = False
    rejection_reason: str | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    stages: dict | None = None
    top_k_results: list | None = None
    results: str | None = None
    error: str | None = None
    created_at: str | None = None


class QueryTraceListResponse(BaseModel):
    """查询追踪列表返回体。"""
    items: list[QueryTraceResponse]
    total: int
    page: int
    page_size: int


class QueryMetricsResponse(BaseModel):
    """查询指标返回体。"""
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_queries: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cache_hit_rate: float = 0.0
    rejection_rate: float = 0.0
    avg_context_precision: float = 0.0
    avg_faithfulness: float = 0.0
    avg_answer_relevancy: float = 0.0


__all__ = [
    "QueryTraceResponse",
    "QueryTraceListResponse",
    "QueryMetricsResponse",
]
