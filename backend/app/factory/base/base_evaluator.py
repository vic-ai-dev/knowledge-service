"""Evaluator 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EvalMetrics:
    hit_rate: float = 0.0
    mrr: float = 0.0
    ndcg: float = 0.0
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    extra: dict = field(default_factory=dict)


class BaseEvaluator(ABC):
    """评估抽象基类。"""

    @abstractmethod
    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[str],
        ground_truth: list[str] | None = None,
        answer: str | None = None,
    ) -> EvalMetrics:
        """执行单次评估。"""
        ...
