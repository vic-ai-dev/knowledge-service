"""EvalRunner — 评估运行器。

从 GoldenTestSet 读取测试用例，通过检索管线运行，
再用配置的评估器打分，最后将结果持久化到 EvaluationResult。
"""

from __future__ import annotations

import uuid
import time
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete

from app.libs.base.base_evaluator import BaseEvaluator, EvalMetrics
from app.libs.evaluator.basic import BasicEvaluator
from app.libs.evaluator.composite import CompositeEvaluator
from app.libs.evaluator.ragas_evaluator import RagasEvaluator
from app.core.query_engine.hybrid_search import HybridSearch
from app.core.query_engine.query_processor import QueryProcessor
from app.models.evaluation import EvaluationResult, GoldenTestSet
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


def _create_default_evaluator(**kwargs: Any) -> CompositeEvaluator:
    """创建默认组合评估器。"""
    return CompositeEvaluator(
        evaluators=[
            BasicEvaluator(**kwargs),
            RagasEvaluator(**kwargs),
        ],
        weights=[1.0, 2.0],  # Ragas 权重更高
    )


class EvalRunner:
    """评估运行器。

    用法:
        runner = EvalRunner(kb_session, rag_session)
        result = await runner.run_single(query="...", ground_truth=["..."])
        # 或
        results = await runner.run_test_set(test_set_id="...")
    """

    def __init__(
        self,
        kb_session: AsyncSession,
        evaluator: BaseEvaluator | None = None,
        **kwargs: Any,
    ):
        self._kb_session = kb_session
        self._evaluator = evaluator or _create_default_evaluator(**kwargs)
        self._searcher = HybridSearch()

    @trace_span()
    async def run_single(
        self,
        query: str,
        ground_truth: list[str] | None = None,
        search_mode: str = "hybrid",
        top_k: int = 10,
        rerank: bool = True,
        test_set_name: str | None = None,
    ) -> tuple[EvalMetrics, Any]:
        """对单条查询执行检索 + 评估。

        Args:
            query: 用户查询。
            ground_truth: 黄金级 chunk 文本列表。
            search_mode: 检索模式（dense/sparse/hybrid）。
            top_k: 检索返回条数。
            rerank: 是否启用重排序。
            test_set_name: 测试集名称（用于记录）。

        Returns:
            EvalMetrics 评估指标。
        """
        # ── 1. 检索 ──
        t0 = time.monotonic()
        processor = QueryProcessor()
        rq = processor.process(
            query_text=query,
            search_mode=search_mode,
            top_k=top_k,
            rerank=rerank,
        )
        search_result = await self._searcher.search(rq)
        search_latency = round((time.monotonic() - t0) * 1000, 2)

        retrieved_texts = [r.text for r in search_result.results]

        # ── 2. 调用 LLM 生成回答 ──
        t1 = time.monotonic()
        context = "\n\n".join(retrieved_texts[:5])
        system_prompt = (
            "你是一个企业知识助手。请根据提供的检索结果回答用户问题。\n\n"
            "检索结果：\n" + context
        )
        llm = getattr(self, '_llm', None)
        if llm is None:
            from app.libs.factory import LLMFactory
            llm = LLMFactory.create()
            self._llm = llm
        llm_response = await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
        )
        llm_latency = round((time.monotonic() - t1) * 1000, 2)
        total_latency = round((time.monotonic() - t0) * 1000, 2)

        # ── 3. 评估 ──
        metrics = await self._evaluator.evaluate(
            query=query,
            retrieved_chunks=retrieved_texts,
            ground_truth=ground_truth,
            answer=llm_response.content,
        )

        # ── 4. 持久化 ──
        result = EvaluationResult(
            metrics={
                "hit_rate": metrics.hit_rate,
                "mrr": metrics.mrr,
                "ndcg": metrics.ndcg,
                "faithfulness": metrics.faithfulness,
                "answer_relevancy": metrics.answer_relevancy,
                "context_precision": metrics.context_precision,
            },
            test_set=test_set_name or "ad_hoc",
            backends_used=dict(
                search_mode=search_mode,
                rerank=rerank,
                top_k=top_k,
                latency_ms=total_latency,
            ),
        )
        self._kb_session.add(result)
        await self._kb_session.flush()

        logger.info(
            "eval_single_complete",
            metadata={
                "query": query[:60],
                "hit_rate": metrics.hit_rate,
                "faithfulness": metrics.faithfulness,
                "answer_relevancy": metrics.answer_relevancy,
                "latency_ms": total_latency,
            },
        )

        return metrics, result.id

    async def run_test_set(
        self,
        test_set_id: str,
        search_mode: str = "hybrid",
        top_k: int = 10,
        rerank: bool = True,
    ) -> list[EvalMetrics]:
        """对 GoldenTestSet 中的全部查询逐一执行评估。

        Args:
            test_set_id: Test Set ID（UUID）。
            search_mode: 检索模式。
            top_k: 返回条数。
            rerank: 是否重排序。

        Returns:
            list[EvalMetrics] 每个查询的评估结果。
        """
        # 加载测试集
        try:
            ts_id = uuid.UUID(test_set_id)
        except ValueError:
            raise ValueError(f"Invalid test_set_id: {test_set_id}")

        stmt = select(GoldenTestSet).where(GoldenTestSet.id == ts_id)
        result = await self._kb_session.execute(stmt)
        test_set: GoldenTestSet | None = result.scalar_one_or_none()
        if test_set is None:
            raise ValueError(f"TestSet not found: {test_set_id}")

        name = test_set.name
        queries = test_set.queries or []
        logger.info("eval_testset_start", metadata={"name": name, "query_count": len(queries)})

        all_metrics = []
        for q in queries:
            query_text = q.get("query", "")
            ground_truth = q.get("ground_truth", [])
            try:
                metrics, result_id = await self.run_single(
                    query=query_text,
                    ground_truth=ground_truth,
                    search_mode=search_mode,
                    top_k=top_k,
                    rerank=rerank,
                    test_set_name=name,
                )
                all_metrics.append(metrics)
            except Exception as e:
                logger.error(
                    "eval_single_failed",
                    error=str(e),
                    metadata={"query": query_text[:60]},
                )

        await self._kb_session.commit()

        # 汇总
        if all_metrics:
            avg_hit = sum(m.hit_rate for m in all_metrics) / len(all_metrics)
            avg_faith = sum(
                (m.faithfulness or 0.0) for m in all_metrics
            ) / len(all_metrics)
            logger.info(
                "eval_testset_done",
                metadata={
                    "name": name,
                    "total_queries": len(queries),
                    "completed": len(all_metrics),
                    "avg_hit_rate": round(avg_hit, 4),
                    "avg_faithfulness": round(avg_faith, 4),
                },
            )

        return all_metrics


__all__ = ["EvalRunner"]
