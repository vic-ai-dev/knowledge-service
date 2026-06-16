"""C1 — Ingestion Pipeline 数据模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.common.enums import IngestionStatus, PipelineStage


@dataclass
class IngestionDocument:
    """正在被摄入的文档。"""
    source_path: str
    doc_type: str  # pdf, md, html
    category: str
    language: str  # zh, en
    title: str | None = None
    file_size: int | None = None
    file_hash: str | None = None
    collection: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    text: str | None = None  # 加载后的原始文本


@dataclass
class ChunkRecord:
    """摄入管线中的 Chunk 记录。"""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str | None = None
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    section_title: str | None = None
    chunk_index: int = 0
    start_offset: int = 0
    end_offset: int = 0
    source_path: str | None = None
    token_count: int = 0
    category: str | None = None
    language: str | None = None
    doc_type: str | None = None
    collection: str = "default"


@dataclass
class StageMetrics:
    """单个 Pipeline 阶段的指标。"""
    stage: str
    duration_ms: float = 0.0
    items_processed: int = 0
    error: str | None = None


@dataclass
class IngestionResult:
    """摄入管线的最终结果。"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str | None = None
    source_path: str = ""
    status: IngestionStatus = IngestionStatus.PENDING
    total_chunks: int = 0
    total_images: int = 0
    errors: list[str] = field(default_factory=list)
    stages: list[StageMetrics] = field(default_factory=list)
    chunks: list[ChunkRecord] = field(default_factory=list)  # 处理后的 Chunk 列表（含 embedding），供后续步骤使用
    trace_id: str = ""


@dataclass
class IngestionProgress:
    """摄入进度（用于回调/WebSocket 推送）。"""
    run_id: str
    stage: PipelineStage = PipelineStage.LOADING
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
