"""核心数据类型契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

@dataclass
class Chunk:
    """文档分块（Chunk）。"""
    id: str = field(default_factory=lambda: str(uuid4()))
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

@dataclass
class DocumentInfo:
    """文档信息（用于 API 返回）。"""
    id: str
    source_path: str
    title: str | None = None
    category: str = ""
    language: str = ""
    doc_type: str = ""
    file_size: int | None = None
    chunk_count: int = 0
    ingested_at: str | None = None
    updated_at: str | None = None

@dataclass
class RetrievalResult:
    """检索结果条目。"""
    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    title: str | None = None
    doc_id: str | None = None

@dataclass
class QueryResult:
    """查询结果。"""
    query: str
    results: list[RetrievalResult] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    total_latency_ms: float = 0.0
    answer: str | None = None
    citations: list[dict] = field(default_factory=list)
    usage: dict | None = None
    llm_model: str | None = None
    rejected: bool = False

@dataclass
class Chunk:
    """文档分块（Chunk）。"""
    id: str = field(default_factory=lambda: str(uuid4()))
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

@dataclass
class DocumentInfo:
    """文档信息（用于 API 返回）。"""
    id: str
    source_path: str
    title: str | None = None
    category: str = ""
    language: str = ""
    doc_type: str = ""
    file_size: int | None = None
    chunk_count: int = 0
    ingested_at: str | None = None
    updated_at: str | None = None

@dataclass
class RetrievalResult:
    """检索结果条目。"""
    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    title: str | None = None
    doc_id: str | None = None
