"""CompositeEvaluator — 组合多个评估器，聚合结果。"""

from __future__ import annotations

from typing import Any

from app.libs.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class CompositeEvaluator(BaseEvaluator):
    """组合评估器。

    将多个评估器（如 BasicEvaluator + RagasEvaluator）组合在一起，
    对同一个输入运行所有评估器，合并结果。

    对于多个评估器都计算的同名指标，取平均值。
    """

    def __init__(self, evaluators: list[BaseEvaluator], **kwargs: Any):
        if not evaluators:
            raise ValueError("CompositeEvaluator requires at least one sub-evaluator")
        self._evaluators = evaluators
        self._weights: list[float] = kwargs.pop("weights", None) or [1.0] * len(evaluators)
        if len(self._weights) != len(evaluators):
            raise ValueError("weights must match evaluators count")

    @trace_span()
    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[str],
        ground_truth: list[str] | None = None,
        answer: str | None = None,
    ) -> EvalMetrics:
        """执行所有子评估器，合并结果。"""
        all_metrics: list[EvalMetrics] = []
        for evaluator in self._evaluators:
            try:
                result = await evaluator.evaluate(
                    query=query,
                    retrieved_chunks=retrieved_chunks,
                    ground_truth=ground_truth,
                    answer=answer,
                )
                all_metrics.append(result)
            except Exception as e:
                logger.warning(
                    "composite_eval_failed",
                    error=str(e),
                    metadata={"evaluator": type(evaluator).__name__},
                )

        if not all_metrics:
            return EvalMetrics(extra={"note": "All sub-evaluators failed"})

        # ── 字段合并：同名字段取加权平均 ──
        total_weight = sum(self._weights[i] for i in range(len(all_metrics)))
        if total_weight == 0:
            total_weight = 1.0

        merged: dict[str, float | None] = {}
        field_names = [
            "hit_rate", "mrr", "ndcg",
            "faithfulness", "answer_relevancy", "context_precision",
        ]
        for field in field_names:
            values = []
            w_sum = 0.0
            for idx, m in enumerate(all_metrics):
                val = getattr(m, field, None)
                if val is not None:
                    w = self._weights[idx] if idx < len(self._weights) else 1.0
                    values.append(val * w)
                    w_sum += w
            if values and w_sum > 0:
                merged[field] = sum(values) / w_sum

        # ── Extra：聚合所有 extra ──
        merged_extra: dict[str, Any] = {}
        for idx, m in enumerate(all_metrics):
            merged_extra[f"eval_{idx}_{type(self._evaluators[idx]).__name__}"] = m.extra

        return EvalMetrics(
            hit_rate=merged.get("hit_rate", 0.0) or 0.0,
            mrr=merged.get("mrr", 0.0) or 0.0,
            ndcg=merged.get("ndcg", 0.0) or 0.0,
            faithfulness=merged.get("faithfulness"),
            answer_relevancy=merged.get("answer_relevancy"),
            context_precision=merged.get("context_precision"),
            extra=merged_extra,
        )


__all__ = ["CompositeEvaluator"]
