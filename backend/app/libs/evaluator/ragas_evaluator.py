"""RagasEvaluator — 使用 ragas 库计算核心指标。

基于 ragas 0.4.3 的 async evaluate（aevaluate），
通过 LangchainLLMWrapper + ChatOpenAI 复用系统配置的 LLM。
预留 deepeval 等后续评估后端接入点（通过 EvaluatorFactory 注册）。
"""

from __future__ import annotations

from typing import Any

from datasets import Dataset
from langchain_openai import ChatOpenAI

from ragas import aevaluate
from ragas.metrics.collections import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.llms.base import LangchainLLMWrapper

from app.libs.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.core.settings import get_settings
from app.common.log import get_logger

logger = get_logger(__name__)

# ── 指标分组 ────────────────────────────────────────────
_METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]
_METRICS_REQUIRE_GT = {context_precision, context_recall}

class RagasEvaluator(BaseEvaluator):
    """基于 ragas 库的评估器。

    自动从 settings.yaml 读取 LLM 配置，通过 LangChain ChatOpenAI
    （OpenAI 兼容接口）驱动 ragas 的 LLM 评估任务。

    Args:
        llm: 可选，传入已经构造好的 LangchainLLMWrapper 或 ChatOpenAI。
              不传时自动从 settings.yaml 读取。
    """

    def __init__(self, **kwargs: Any):
        self._llm = kwargs.get("llm") or self._build_llm()

    def _build_llm(self) -> LangchainLLMWrapper:
        """根据系统配置构建 ragas 可用的 LLM。"""
        cfg = get_settings().llm
        api_key = (
            cfg.api_key.get_secret_value()
            if hasattr(cfg.api_key, "get_secret_value")
            else cfg.api_key
        )
        chat = ChatOpenAI(
            model=cfg.model,
            api_key=api_key,
            base_url=cfg.base_url,
            temperature=getattr(cfg, "temperature", 0.0),
            max_tokens=getattr(cfg, "max_tokens", 4096),
        )
        return LangchainLLMWrapper(chat)

    # ── 可选配置接口（供工厂使用）──
    @property
    def requires_llm(self) -> bool:
        return True

    @property
    def requires_embeddings(self) -> bool:
        return False
    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[str],
        ground_truth: list[str] | None = None,
        answer: str | None = None,
    ) -> EvalMetrics:
        """执行 ragas 评估。

        Args:
            query: 用户查询。
            retrieved_chunks: 检索到的 chunk 文本列表。
            ground_truth: 黄金级相关文本列表（可选）。
            answer: LLM 生成的回答（必需）。

        Returns:
            EvalMetrics: 包含 faithfulness / answer_relevancy / context_precision / context_recall。
        """
        if not answer:
            raise ValueError("RagasEvaluator requires `answer` parameter")

        metrics = list(_METRICS)

        # 无 ground_truth 时跳过需要它的指标
        if not ground_truth:
            metrics = [m for m in metrics if m not in _METRICS_REQUIRE_GT]

        # ── 构建 Hugging Face Dataset ──
        data: dict[str, list] = {
            "question": [query],
            "contexts": [retrieved_chunks],
            "answer": [answer],
        }
        if ground_truth:
            data["ground_truth"] = [ground_truth]

        dataset = Dataset.from_dict(data)

        # ── 调用 ragas ──
        logger.info(
            "ragas_eval_start",
            message="开始 ragas 评估",
            metadata={
                "metrics": [m.name for m in metrics],
                "has_gt": bool(ground_truth),
                "llm_model": get_settings().llm.model,
            },
        )

        try:
            result = await aevaluate(
                dataset=dataset,
                metrics=metrics,
                llm=self._llm,
                raise_exceptions=True,
            )
        except Exception as e:
            logger.error("ragas_eval_failed", error=str(e))
            return EvalMetrics(
                faithfulness=None,
                answer_relevancy=None,
                context_precision=None,
                context_recall=None,
                extra={
                    "error": str(e),
                    "ragas_error": True,
                },
            )

        # ── 提取分数 ──
        faithfulness_score = (
            float(result["faithfulness"][0]) if "faithfulness" in result else None
        )
        relevancy_score = (
            float(result["answer_relevancy"][0]) if "answer_relevancy" in result else None
        )
        precision_score = (
            float(result["context_precision"][0]) if "context_precision" in result else None
        )
        recall_score = (
            float(result["context_recall"][0]) if "context_recall" in result else None
        )

        logger.info(
            "ragas_eval_done",
            message="ragas 评估完成",
            metadata={
                "faithfulness": faithfulness_score,
                "answer_relevancy": relevancy_score,
                "context_precision": precision_score,
                "context_recall": recall_score,
            },
        )

        return EvalMetrics(
            hit_rate=0.0,
            mrr=0.0,
            ndcg=0.0,
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            context_precision=precision_score,
            context_recall=recall_score,
            extra={
                "ragas_model": get_settings().llm.model,
                "ragas_version": "0.4.3",
            },
        )

__all__ = ["RagasEvaluator"]
