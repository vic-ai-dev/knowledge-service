"""D6 — Reranker：检索层重排序编排。

通过 RerankerFactory 创建重排序器，对候选结果执行深度排序，
失败时回退到融合分数排序。
"""

from __future__ import annotations

import time
from typing import Any

from app.core.query_engine.query_types import RankedChunk
from app.libs.factory import RerankerFactory
from app.common.log import get_logger

logger = get_logger(__name__)

class RerankerError(RuntimeError):
    """Reranker 编排通用异常。"""
    pass

class QueryReranker:
    """检索层重排序编排器。

    职责：
      1. 通过 RerankerFactory 获取重排序器
      2. 将 RankedChunk 转换为 Reranker 所需的 dict 格式
      3. 执行重排序
      4. 失败时自动回退到原始融合排序

    :param rerank_backend: 重排序后端（None 则使用配置默认）。
    :param kwargs: 传递给 RerankerFactory.create() 的额外参数。
    """

    def __init__(
        self,
        rerank_backend: str | None = None,  # cross_encoder | None (None = use config default)
        **kwargs: Any,
    ):
        self._rerank_backend = rerank_backend
        self._kwargs = kwargs
        self._reranker = None

    # ── 延迟初始化 ──────────────────────────────────────────

    def _get_reranker(self):
        if self._reranker is None:
            self._reranker = RerankerFactory.create(
                backend=self._rerank_backend,
                **self._kwargs,
            )
        return self._reranker

    # ── 输入校验 ──────────────────────────────────────────────

    def _validate_inputs(
        self,
        query: str,
        candidates: list[RankedChunk],
    ) -> None:
        if not query or not query.strip():
            raise RerankerError("query cannot be empty")
        if not candidates:
            raise RerankerError("candidates list cannot be empty")

    # ── RankedChunk → dict 转换 ──────────────────────────────

    @staticmethod
    def _to_dict(chunk: RankedChunk) -> dict:
        return {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "score": chunk.fusion_score or chunk.score,
            "metadata": chunk.metadata,
            "source_path": chunk.source_path,
        }

    @staticmethod
    def _from_rerank_result(
        result,
        original_chunks: dict[str, RankedChunk],
    ) -> RankedChunk:
        """将 Reranker 返回的 RerankResult 转换回 RankedChunk。

        保留原始阶段的评分信息。
        """
        chunk_id = result.chunk_id
        original = original_chunks.get(chunk_id)

        ranked = RankedChunk(
            chunk_id=chunk_id,
            text=result.text,
            metadata=result.metadata or {},
            rerank_score=result.score,
            source_path=original.source_path if original else None,
            doc_id=original.doc_id if original else None,
            category=original.category if original else None,
            language=original.language if original else None,
            doc_type=original.doc_type if original else None,
            dense_score=original.dense_score if original else 0.0,
            sparse_score=original.sparse_score if original else 0.0,
            fusion_score=original.fusion_score if original else 0.0,
        )
        ranked.score = result.score
        return ranked

    # ── 核心方法 ──────────────────────────────────────────────
    async def rerank(
        self,
        query: str,
        candidates: list[RankedChunk],
        top_k: int | None = None,
    ) -> list[RankedChunk]:
        """执行重排序。

        Args:
            query: 原始查询文本。
            candidates: 待排序的候选结果。
            top_k: 返回的最大结果数（None 使用 Reranker 配置值）。

        Returns:
            重排序后的 RankedChunk 列表。

        异常安全：如果 Reranker 调用失败，自动回退到原始排序。
        """
        self._validate_inputs(query, candidates)
        t0 = time.monotonic()
        top_k = top_k or len(candidates)

        # 构建原始 chunk 索引（用于回退）
        chunk_map = {c.chunk_id: c for c in candidates}

        # 转换为 Reranker 支持的 dict 格式
        dict_candidates = [self._to_dict(c) for c in candidates]

        # 尝试执行重排序
        reranker = self._get_reranker()

        try:
            results = await reranker.rerank(
                query=query,
                candidates=dict_candidates,
                top_k=top_k,
            )

            ranked = [
                self._from_rerank_result(r, chunk_map)
                for r in results
            ]

            elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

            logger.info(
                "query_rerank_done",
                metadata={
                    "candidates": len(candidates),
                    "final": len(ranked),
                    "latency_ms": elapsed_ms,
                },
            )

            return ranked

        except Exception as e:
            # 回退到原始排序
            logger.warning(
                "query_rerank_fallback",
                metadata={
                    "error": str(e),
                    "fallback": len(candidates),
                },
            )
            # 按 fusion_score 降序取 top_k
            candidates.sort(
                key=lambda c: c.fusion_score or c.score,
                reverse=True,
            )
            return candidates[:top_k]

__all__ = ["QueryReranker", "RerankerError"]
