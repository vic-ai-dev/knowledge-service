"""核心数据类型契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


# ── 文档类型 ─────────────────────────────────────────────────

DOC_TYPE_PDF = "pdf"
DOC_TYPE_MD = "md"
DOC_TYPE_HTML = "html"
VALID_DOC_TYPES = {DOC_TYPE_PDF, DOC_TYPE_MD, DOC_TYPE_HTML}

CATEGORY_EMPLOYEE_HANDBOOK = "employee_handbook"
CATEGORY_COMPLIANCE = "compliance"
CATEGORY_TECHNICAL_SPEC = "technical_spec"
CATEGORY_ARCHITECTURE = "architecture"
VALID_CATEGORIES = {
    CATEGORY_EMPLOYEE_HANDBOOK,
    CATEGORY_COMPLIANCE,
    CATEGORY_TECHNICAL_SPEC,
    CATEGORY_ARCHITECTURE,
}

LANGUAGE_ZH = "zh"
LANGUAGE_EN = "en"
VALID_LANGUAGES = {LANGUAGE_ZH, LANGUAGE_EN}

SEARCH_MODE_VECTOR_ONLY = "vector_only"
SEARCH_MODE_HYBRID = "hybrid"
VALID_SEARCH_MODES = {SEARCH_MODE_VECTOR_ONLY, SEARCH_MODE_HYBRID}

RERANK_NONE = "none"
RERANK_CROSS_ENCODER = "cross_encoder"
RERANK_LLM = "llm"
VALID_RERANK_BACKENDS = {RERANK_NONE, RERANK_CROSS_ENCODER, RERANK_LLM}


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
    collection: str = "default"
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
    source_path: str | None = None


@dataclass
class QueryResult:
    """查询结果。"""
    query: str
    results: list[RetrievalResult] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    total_latency_ms: float = 0.0
    answer: str | None = None
    citations: list[dict] = field(default_factory=list)
