"""Query ORM 模型 — 查询追踪与缓存（knowledge 库）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import KnowledgeBase


class QueryTrace(KnowledgeBase):
    __tablename__ = "query_traces"

    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    collection: Mapped[str] = mapped_column(String, default="default")
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    stages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    top_k_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QueryCache(KnowledgeBase):
    __tablename__ = "query_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    rerank: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now() + text("INTERVAL '1 hour'"),
    )


__all__ = ["QueryTrace", "QueryCache"]
