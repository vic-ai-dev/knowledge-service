"""Ingestion Pydantic Schemas。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IngestionHistoryResponse(BaseModel):
    """摄入历史返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_hash: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    status: str | None = None
    category: str | None = None
    language: str | None = None
    doc_type: str | None = None
    chunk_count: int = 0
    error_msg: str | None = None
    processed_at: str | None = None


class IngestionHistoryListResponse(BaseModel):
    """摄入历史列表返回体。"""
    items: list[IngestionHistoryResponse]
    total: int
    page: int
    page_size: int


class IngestionTraceResponse(BaseModel):
    """摄入追踪返回体。"""
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    source_path: str
    collection: str = "default"
    total_latency_ms: int | None = None
    status: str | None = None
    total_chunks: int | None = None
    total_images: int | None = None
    stages: dict | None = None
    error: str | None = None
    created_at: str | None = None


class IngestionTraceListResponse(BaseModel):
    """摄入追踪列表返回体。"""
    items: list[IngestionTraceResponse]
    total: int
    page: int
    page_size: int


__all__ = [
    "IngestionHistoryResponse",
    "IngestionHistoryListResponse",
    "IngestionTraceResponse",
    "IngestionTraceListResponse",
]
