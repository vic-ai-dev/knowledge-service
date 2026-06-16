"""Reranker 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankResult:
    chunk_id: str
    text: str
    score: float
    metadata: dict | None = None


class BaseReranker(ABC):
    """重排序抽象基类。"""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """对候选结果重排序。"""
        ...


class NoOpReranker(BaseReranker):
    """无操作 Reranker（直接返回原序）。"""

    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        if top_k:
            candidates = candidates[:top_k]
        return [
            RerankResult(
                chunk_id=c.get("chunk_id", ""),
                text=c.get("text", ""),
                score=c.get("score", 0.0),
                metadata=c.get("metadata"),
            )
            for c in candidates
        ]
