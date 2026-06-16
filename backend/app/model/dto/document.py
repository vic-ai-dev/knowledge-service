"""Document Pydantic Schemas。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """文档返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_path: str
    title: str | None = None
    category: str
    language: str
    doc_type: str
    file_size: int | None = None
    file_hash: str | None = None
    chunk_count: int = 0
    image_count: int = 0
    status: str | None = None
    ingested_at: str | None = None
    updated_at: str | None = None
    is_deleted: bool = False


class DocumentUpdate(BaseModel):
    """文档 metadata 更新。"""
    title: str | None = None
    category: str | None = None
    language: str | None = None


class DocumentListResponse(BaseModel):
    """文档列表返回体。"""
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentStatsResponse(BaseModel):
    """文档统计返回体。"""
    total_documents: int = 0
    total_chunks: int = 0
    total_categories: int = 0
    total_categories: int = 0
    total_size_bytes: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_language: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)


__all__ = [
    "DocumentResponse",
    "DocumentUpdate",
    "DocumentListResponse",
    "DocumentStatsResponse",
]
