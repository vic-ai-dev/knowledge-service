"""RagasEvaluator — LLM Judge 驱动的评估器。

不使用 ragas 库（因其依赖链过于复杂），而是通过 LLM 作为 Judge
直接计算 faithfulness / answer_relevancy，并结合 BasicEvaluator
计算 context_precision / context_recall。
"""

from __future__ import annotations

import json
import math
from typing import Any

from app.libs.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.libs.factory import LLMFactory
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)

# ── Prompt 模板 ──────────────────────────────────────────

FAITHFULNESS_PROMPT = """你是一位公正的评估员。你的任务是判断以下「回答」是否完全基于给定的「上下文」生成。

评分规则：
- 1.0：回答完全基于上下文，没有添加未被上下文支持的信息
- 0.5：回答大部分基于上下文，但有一些未被明确支持的细节
- 0.0：回答与上下文不一致，或添加了大量未被支持的信息

请只返回一个 0.0 到 1.0 之间的数字，无需任何解释。

上下文：
{context}

回答：
{answer}

评分："""

ANSWER_RELEVANCY_PROMPT = """你是一位公正的评估员。你的任务是判断以下「回答」是否与「问题」直接相关。

评分规则：
- 1.0：回答直接回答了问题，内容完全相关
- 0.5：回答部分相关，但没有直接回答核心问题
- 0.0：回答与问题无关，或完全不相关

请只返回一个 0.0 到 1.0 之间的数字，无需任何解释。

问题：
{question}

回答：
{answer}

评分："""


def _parse_score(text: str) -> float:
    """从 LLM 回复中提取评分 (0.0-1.0)。"""
    try:
        # 尝试直接解析数字
        cleaned = text.strip().strip('"').strip("'")
        score = float(cleaned)
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        # 尝试从文本中提取数字
        import re
        matches = re.findall(r"(\d+\.?\d*)", text)
        if matches:
            score = float(matches[0])
            if score > 1.0:
                score = score / 100.0  # 可能是 85 这种格式
            return max(0.0, min(1.0, score))
        return 0.5  # 默认中立


class RagasEvaluator(BaseEvaluator):
    """LLM Judge 评估器，计算 Ragas 核心指标。"""

    def __init__(self, **kwargs: Any):
        self._llm = kwargs.pop("llm", None) or LLMFactory.create()

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
            query: 用户查询。
            retrieved_chunks: 检索到的 chunk 文本列表（按相关性降序）。
            ground_truth: 黄金级相关 chunk（可选，用于 context 指标）。
            answer: LLM 生成的回答（可选，用于 faithfulness/answer_relevancy）。
        """
        context = "\n\n".join(retrieved_chunks[:5]) if retrieved_chunks else ""
        gt_set = set(ground_truth) if ground_truth else set()

        # ── Faithfulness（需要 answer + context）──
        faithfulness: float | None = None
        if answer and context:
            try:
                resp = await self._llm.generate(
                    messages=[
                        {"role": "user", "content": FAITHFULNESS_PROMPT.format(
                            context=context[:3000], answer=answer[:1000]
                        )},
                    ],
                )
                faithfulness = _parse_score(resp.content)
                logger.info("eval_faithfulness", score=faithfulness, metadata={})
            except Exception as e:
                logger.warning("eval_faithfulness_failed", error=str(e))
                faithfulness = 0.0

        # ── Answer Relevancy（需要 question + answer）──
        answer_relevancy: float | None = None
        if answer:
            try:
                resp = await self._llm.generate(
                    messages=[
                        {"role": "user", "content": ANSWER_RELEVANCY_PROMPT.format(
                            question=query, answer=answer[:1000]
                        )},
                    ],
                )
                answer_relevancy = _parse_score(resp.content)
                logger.info("eval_answer_relevancy", score=answer_relevancy, metadata={})
            except Exception as e:
                logger.warning("eval_answer_relevancy_failed", error=str(e))
                answer_relevancy = 0.0

        # ── Context Precision（hit_rate on retrieved chunks vs ground_truth）──
        context_precision: float | None = None
        context_recall: float | None = None
        if gt_set:
            k = min(len(retrieved_chunks), 10)
            hits = sum(1 for c in retrieved_chunks[:k] if c in gt_set)
            context_precision = hits / k if k > 0 else 0.0
            context_recall = hits / len(gt_set) if gt_set else 0.0

        return EvalMetrics(
            hit_rate=context_recall or 0.0,
            mrr=0.0,
            ndcg=0.0,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            extra={
                "context_recall": context_recall,
                "llm_provider": self._llm.model,
                "note": "Faithfulness & AnswerRelevancy via LLM Judge; Context via overlap",
            },
        )


__all__ = ["RagasEvaluator"]
