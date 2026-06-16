"""领域枚举常量 — 统一管理所有状态、类型、模式。

避免魔法字符串在代码中飘散，所有状态值集中定义，Schema / DB / API 共用。
"""

from __future__ import annotations

from enum import Enum, unique


# ── 文档分类 ─────────────────────────────────────────────

@unique
class Category(str, Enum):
    """知识库文档分类。"""
    EMPLOYEE_HANDBOOK = "employee_handbook"  # 员工手册
    COMPLIANCE = "compliance"                # 合规指南
    TECHNICAL_SPEC = "technical_spec"        # 技术规范
    ARCHITECTURE = "architecture"            # 架构文档


@unique
class Language(str, Enum):
    """文档语言。"""
    ZH = "zh"
    EN = "en"


@unique
class DocType(str, Enum):
    """文档文件类型。"""
    PDF = "pdf"
    MD = "md"
    HTML = "html"


# ── 检索模式 ─────────────────────────────────────────────

@unique
class SearchMode(str, Enum):
    """检索模式（用户/前端选择）。"""
    VECTOR_ONLY = "vector_only"  # 仅向量检索（Dense）
    HYBRID = "hybrid"            # 混合检索（Dense + Sparse）


@unique
class SearchStrategy(str, Enum):
    """检索策略（引擎执行层，记录实际执行的检索方式）。"""
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@unique
class RerankBackend(str, Enum):
    """重排序后端。"""
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    LLM = "llm"


@unique
class FusionAlgorithm(str, Enum):
    """融合算法。"""
    RRF = "rrf"


# ── 摄入相关状态 ─────────────────────────────────────────

@unique
class IngestionStatus(str, Enum):
    """文件摄入状态（含 pipeline 内部和 DB 持久化）。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@unique
class IngestionTraceStatus(str, Enum):
    """Ingestion 追踪记录状态（ingestion_traces 表）。"""
    COMPLETED = "completed"
    FAILED = "failed"


# ── Pipeline 阶段 ────────────────────────────────────────

@unique
class PipelineStage(str, Enum):
    """Pipeline 阶段 — 合并摄入管线与查询管线。"""
    LOADING = "loading"
    CHECKING = "checking"
    SPLITTING = "splitting"
    TRANSFORMING = "transforming"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    QUERY_PROCESSING = "query_processing"
    DENSE_SEARCH = "dense_search"
    SPARSE_SEARCH = "sparse_search"
    FUSION = "fusion"
    RERANK = "rerank"
    RESPONSE_BUILDING = "response_building"
    COMPLETED = "completed"
    FAILED = "failed"


# ── 评估 ─────────────────────────────────────────────────

@unique
class EvaluationRunStatus(str, Enum):
    """评估运行状态（API 层使用）。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


# ── 集合（验证辅助） ──────────────────────────────────────

CATEGORY_VALUES = {e.value for e in Category}
LANGUAGE_VALUES = {e.value for e in Language}
DOCTYPE_VALUES = {e.value for e in DocType}
SEARCH_MODE_VALUES = {e.value for e in SearchMode}
SEARCH_STRATEGY_VALUES = {e.value for e in SearchStrategy}
RERANK_BACKEND_VALUES = {e.value for e in RerankBackend}
INGESTION_STATUS_VALUES = {e.value for e in IngestionStatus}
INGESTION_TRACE_STATUS_VALUES = {e.value for e in IngestionTraceStatus}
PIPELINE_STAGE_VALUES = {e.value for e in PipelineStage}
EVALUATION_RUN_STATUS_VALUES = {e.value for e in EvaluationRunStatus}

__all__ = [
    "Category",
    "Language",
    "DocType",
    "SearchMode",
    "SearchStrategy",
    "RerankBackend",
    "FusionAlgorithm",
    "IngestionStatus",
    "IngestionTraceStatus",
    "PipelineStage",
    "EvaluationRunStatus",
    "CATEGORY_VALUES",
    "LANGUAGE_VALUES",
    "DOCTYPE_VALUES",
    "SEARCH_MODE_VALUES",
    "SEARCH_STRATEGY_VALUES",
    "RERANK_BACKEND_VALUES",
    "INGESTION_STATUS_VALUES",
    "INGESTION_TRACE_STATUS_VALUES",
    "PIPELINE_STAGE_VALUES",
    "EVALUATION_RUN_STATUS_VALUES",
]
