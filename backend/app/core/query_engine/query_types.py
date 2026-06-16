"""查询引擎核心数据类型。"""

from __future__ import annotations

from app.common.enums import SearchMode, SEARCH_MODE_VALUES

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalQuery:
    """处理后的检索查询。"""
    query_text: str
    search_mode: str = SearchMode.HYBRID.value  # SearchMode: vector_only | hybrid
    top_k: int = 10
    filters: dict[str, Any] | None = None
    rerank: bool = True

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {self.top_k}")
        if self.search_mode not in SEARCH_MODE_VALUES:
            raise ValueError(f"invalid search_mode: {self.search_mode}")


@dataclass
class RankedChunk:
    """检索管道中的中间结果，带各阶段评分。"""
    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0               # 最终分数
    source_path: str | None = None
    doc_id: str | None = None
    collection: str = "default"
    category: str | None = None
    language: str | None = None
    doc_type: str | None = None

    # 各阶段评分
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0


__all__ = [
    "RetrievalQuery",
    "RankedChunk",
]
