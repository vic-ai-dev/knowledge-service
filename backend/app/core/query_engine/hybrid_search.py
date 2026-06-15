"""D5 — HybridSearch：混合检索编排器。

编排精排：Dense → Sparse → RRF Fusion → Rerank。
填充 QueryResult 并附带延迟追踪。
"""

from __future__ import annotations

import time
from typing import Any

from app.core.query_engine.dense_retriever import DenseRetriever
from app.core.query_engine.query_types import RankedChunk, RetrievalQuery
from app.core.query_engine.reranker import QueryReranker
from app.core.query_engine.rrf_fusion import RRFFusion
from app.core.query_engine.sparse_retriever import SparseRetriever
from app.core.types import QueryResult, RetrievalResult
from app.common.log import get_logger
from app.observability.instrumentation import trace_span
from app.observability.progress import (
    NoOpProgressCallback,
    PipelineProgress,
    PipelineStage,
    ProgressCallback,
)

logger = get_logger(__name__)


class HybridSearchError(RuntimeError):
    """HybridSearch 通用异常。"""
    pass


class HybridSearch:
    """混合检索编排器。

    根据查询模式（vector_only / hybrid）执行检索路线，
    支持可插拔的重排序。

    :param dense_retriever: DenseRetriever 实例。
    :param sparse_retriever: SparseRetriever 实例。
    :param rrf_fusion: RRFFusion 实例。
    :param query_reranker: QueryReranker 实例。
    :param progress_callback: 进度回调。
    """

    def __init__(
        self,
        dense_retriever: DenseRetriever | None = None,
        sparse_retriever: SparseRetriever | None = None,
        rrf_fusion: RRFFusion | None = None,
        query_reranker: QueryReranker | None = None,
        progress_callback: ProgressCallback | None = None,
    ):
        self._dense = dense_retriever or DenseRetriever()
        self._sparse = sparse_retriever or SparseRetriever()
        self._fusion = rrf_fusion or RRFFusion()
        self._reranker = query_reranker or QueryReranker()
        self._progress = progress_callback or NoOpProgressCallback()

    # ── 结果转换 ──────────────────────────────────────────────

    @staticmethod
    def _to_retrieval_results(chunks: list[RankedChunk]) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk_id=c.chunk_id,
                text=c.text,
                metadata=c.metadata,
                score=c.score,
                source_path=c.source_path,
            )
            for c in chunks
        ]

    # ── 核心方法 ──────────────────────────────────────────────

    @trace_span("retrieval", "hybrid_search")
    async def search(
        self,
        query: RetrievalQuery,
    ) -> QueryResult:
        """执行检索。

        Args:
            query: 已处理的检索查询对象。

        Returns:
            QueryResult，包含结果列表与追踪信息。

        Raises:
            HybridSearchError: 检索过程中发生错误。
        """
        t0 = time.monotonic()

        self._progress(PipelineProgress(
            run_id="search",
            stage=PipelineStage.QUERY_PROCESSING,
            progress=0.0,
            message=f"Searching: {query.query_text[:60]}",
        ))

        try:
            # ── 稠密检索（所有模式均需） ────────────────────
            self._progress(PipelineProgress(
                run_id="search",
                stage=PipelineStage.DENSE_SEARCH,
                progress=0.2,
                message="Dense retrieval",
            ))

            dense_results = await self._dense.retrieve(
                query_text=query.query_text,
                top_k=query.top_k,
                filters=query.filters,
            )

            # ── 稀疏检索（hybrid 模式） ─────────────────────
            sparse_results: list[RankedChunk] = []
            if query.search_mode == "hybrid":
                self._progress(PipelineProgress(
                    run_id="search",
                    stage=PipelineStage.SPARSE_SEARCH,
                    progress=0.4,
                    message="Sparse retrieval",
                ))

                sparse_results = await self._sparse.retrieve(
                    query_text=query.query_text,
                    top_k=query.top_k,
                    filters=query.filters,
                )

            # ── RRF 融合（hybrid 模式） ─────────────────────
            self._progress(PipelineProgress(
                run_id="search",
                stage=PipelineStage.FUSION,
                progress=0.6,
                message="RRF fusion",
            ))

            if query.search_mode == "hybrid" and dense_results and sparse_results:
                fused = self._fusion.fuse(
                    dense_results=dense_results,
                    sparse_results=sparse_results,
                    top_k=query.top_k,
                )
            else:
                # vector_only 或无匹配模式：直接使用 dense 结果
                fused = dense_results[:query.top_k]

            # ── Rerank ──────────────────────────────────────
            if query.rerank and fused:
                self._progress(PipelineProgress(
                    run_id="search",
                    stage=PipelineStage.RERANK,
                    progress=0.8,
                    message=f"Reranking {len(fused)} candidates",
                ))
                fused = await self._reranker.rerank(
                    query=query.query_text,
                    candidates=fused,
                    top_k=query.top_k,
                )

            # ── 构建结果 ────────────────────────────────────
            results = self._to_retrieval_results(fused)
            total_latency = round((time.monotonic() - t0) * 1000, 2)

            self._progress(PipelineProgress(
                run_id="search",
                stage=PipelineStage.COMPLETED,
                progress=1.0,
                message=f"Done: {len(results)} results in {total_latency}ms",
                total=len(results),
            ))

            logger.info(
                "hybrid_search_done",
                event_type="retrieval",
                metadata={
                    "search_mode": query.search_mode,
                    "dense_results": len(dense_results),
                    "sparse_results": len(sparse_results),
                    "final_results": len(results),
                    "latency_ms": total_latency,
                },
            )

            return QueryResult(
                query=query.query_text,
                results=results,
                total_latency_ms=total_latency,
            )

        except Exception as e:
            self._progress(PipelineProgress(
                run_id="search",
                stage=PipelineStage.FAILED,
                progress=1.0,
                message=f"Failed: {e}",
            ))
            logger.error(
                "hybrid_search_error",
                event_type="retrieval",
                error=str(e),
                metadata={"search_mode": query.search_mode},
            )
            raise HybridSearchError(str(e)) from e


__all__ = ["HybridSearch", "HybridSearchError"]
