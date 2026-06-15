"""
Basic Evaluator 实现。

Computes standard retrieval metrics without external evaluation frameworks:
    - hit_rate
    - mrr (Mean Reciprocal Rank)
    - ndcg (Normalized Discounted Cumulative Gain)

Faithfulness and answer_relevancy require an LLM judge and are left as None
for now (returned as 0.0 with a note in extra).
"""

from __future__ import annotations

import math
from typing import Any

from app.libs.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class EvaluatorError(ValueError):
    """Evaluator 输入校验异常。"""
    pass


class BasicEvaluator(BaseEvaluator):
    """基础评估器，直接计算指标（无外部依赖）。"""

    def __init__(self, **kwargs: Any):
        self._k = kwargs.get("k", 10)

    def _validate_inputs(
        self,
        query: str,
        retrieved_chunks: list[str],
    ) -> None:
        if not query or not query.strip():
            raise EvaluatorError("query cannot be empty")
        if not retrieved_chunks:
            raise EvaluatorError("retrieved_chunks list cannot be empty")

    @trace_span()
    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[str],
        ground_truth: list[str] | None = None,
        answer: str | None = None,
    ) -> EvalMetrics:
        """执行评估。

        Args:
            query: 用户查询（当前仅用于记录）。
            retrieved_chunks: 检索到的 chunk 文本列表（按相关性降序）。
            ground_truth: 黄金级相关 chunk 文本列表。
            answer: LLM 生成的回答（用于 faithfulness 评估）。
        """
        self._validate_inputs(query, retrieved_chunks)
        # 如果没有 ground_truth，只返回空指标
        if not ground_truth:
            return EvalMetrics(
                extra={"note": "No ground_truth provided, retrieval-only metrics unavailable"},
            )

        gt_set = set(ground_truth)

        # ── Hit Rate ──
        hits = 0
        for chunk in retrieved_chunks[:self._k]:
            if chunk in gt_set:
                hits += 1
        hit_rate = hits / len(gt_set) if gt_set else 0.0

        # ── MRR ──
        reciprocal_rank = 0.0
        for i, chunk in enumerate(retrieved_chunks[:self._k]):
            if chunk in gt_set:
                reciprocal_rank = 1.0 / (i + 1)
                break

        # ── NDCG ──
        # Binary relevance: 1 if in ground_truth, 0 otherwise
        relevance = [
            1.0 if chunk in gt_set else 0.0
            for chunk in retrieved_chunks[:self._k]
        ]
        dcg = sum(
            rel / math.log2(i + 2) for i, rel in enumerate(relevance)
        )
        ideal_relevance = sorted(relevance, reverse=True)
        idcg = sum(
            rel / math.log2(i + 2) for i, rel in enumerate(ideal_relevance)
        )
        ndcg = dcg / idcg if idcg > 0 else 0.0

        return EvalMetrics(
            hit_rate=hit_rate,
            mrr=reciprocal_rank,
            ndcg=ndcg,
            extra={
                "k": self._k,
                "retrieved_count": len(retrieved_chunks),
                "ground_truth_count": len(gt_set),
                "note_advanced_metrics": (
                    "faithfulness and answer_relevancy require LLM judge; "
                    "not computed in BasicEvaluator"
                ),
            },
        )
