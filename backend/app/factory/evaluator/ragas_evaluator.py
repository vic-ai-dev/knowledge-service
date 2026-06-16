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
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.llms.base import LangchainLLMWrapper
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from langchain_openai import OpenAIEmbeddings

from app.factory.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.common.settings import get_settings
from app.common.log import get_logger

logger = get_logger(__name__)

# ── 指标分组 ────────────────────────────────────────────
_METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]
# Use metric names for comparison (instances are not hashable)
_METRICS_REQUIRE_GT_NAMES = {"context_precision", "context_recall"}
_METRICS_REQUIRE_EMBEDDINGS_NAMES = {"answer_relevancy", "context_precision", "context_recall"}

class RagasEvaluator(BaseEvaluator):
    """基于 ragas 库的评估器。

    自动从 settings.yaml 读取 LLM 配置，通过 LangChain ChatOpenAI
    （OpenAI 兼容接口）驱动 ragas 的 LLM 评估任务。

    Args:
        llm: 可选，传入已经构造好的 LangchainLLMWrapper 或 ChatOpenAI。
              不传时自动从 settings.yaml 读取。
    """

    def __init__(self, **kwargs: Any):
        self._llm = kwargs.get("llm") or None  # 延迟到 evaluate() 时初始化，避免多次调用状态污染

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

    def _build_embeddings(self):
        """构建 ragas 可用的 Embeddings。

        目前 ragas v0.4.3 的 LangchainEmbeddingsWrapper 仅支持 OpenAI 兼容格式。
        Ollama 等非 OpenAI 端点的 embedding 暂不兼容，导致 400 错误。
        场景景暂时返回 None，跳过需要 embedding 的指标（context_precision/context_recall）。
        待 ragas 升级或嵌入自定义 Wrapper 后恢复。
        """
        cfg = get_settings().embedding
        if cfg.provider == "ollama":
            return None
        try:
            from langchain_openai import OpenAIEmbeddings
            from ragas.embeddings.base import LangchainEmbeddingsWrapper
            if not cfg.api_key:
                return None
            client = OpenAIEmbeddings(
                model=cfg.model,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
            )
            return LangchainEmbeddingsWrapper(client)
        except Exception:
            return None

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

        # ── 构建 Hugging Face Dataset ──
        data: dict[str, list] = {
            "question": [query],
            "contexts": [retrieved_chunks],
            "answer": [answer],
        }
        if ground_truth:
            # ragas 0.4.3 的 ground_truth 是字符串，不是列表
            # ragas 0.4.3 数据集要求 ground_truths 为 list[list[str]]
            # ragas 0.4.3 context_precision 要求列名 reference (字符串)
            data["reference"] = [ground_truth[0]]

        dataset = Dataset.from_dict(data)

        # ── 延迟初始化 LLM（每次 evaluate 都重建，避免状态污染） ──
        self._llm = self._build_llm()
        embeddings = self._build_embeddings()

        metrics = list(_METRICS)
        if not ground_truth:
            metrics = [m for m in metrics if m.name not in _METRICS_REQUIRE_GT_NAMES]
        if embeddings is None:
            # 无 embedding 可用时移除需要 embedding 的指标
            metrics = [m for m in metrics if m.name not in _METRICS_REQUIRE_EMBEDDINGS_NAMES]
            logger.info("ragas_metrics_filtered", metadata={"metrics": [m.name for m in metrics], "reason": "no_embeddings"})

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
                embeddings=embeddings,
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
            float(result["faithfulness"]) if "faithfulness" in result else None
        )
        relevancy_score = (
            float(result["answer_relevancy"]) if "answer_relevancy" in result else None
        )
        precision_score = (
            float(result["context_precision"]) if "context_precision" in result else None
        )
        recall_score = (
            float(result["context_recall"]) if "context_recall" in result else None
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
