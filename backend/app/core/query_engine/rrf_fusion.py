"""D4 — RRF Fusion：倒数排序融合。

使用 Reciprocal Rank Fusion (RRF) 算法合并稠密和稀疏检索结果。
标准 RRF 公式：
    score = 1 / (RRF_K + rank(密集)) + 1 / (RRF_K + rank(稀疏))

默认 RRF_K = 60（经验值，在 TREC 评测中表现稳定）。
"""

from __future__ import annotations

from app.core.query_engine.query_types import RankedChunk
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class RRFFusionError(RuntimeError):
    """RRF 融合通用异常。"""
    pass


class RRFFusion:
    """倒数排序融合 (RRF) 处理器。

    将稠密和稀疏两路检索结果按 chunk_id 合并排序。

    :param rrf_k: RRF 平滑参数（默认 60）。
    """

    def __init__(self, rrf_k: int = 60):
        if rrf_k < 1:
            raise RRFFusionError(f"rrf_k must be >= 1, got {rrf_k}")
        self._rrf_k = rrf_k

    # ── 输入校验 ──────────────────────────────────────────────

    def _validate_inputs(
        self,
        dense_results: list[RankedChunk],
        sparse_results: list[RankedChunk],
    ) -> None:
        if not dense_results and not sparse_results:
            raise RRFFusionError(
                "both dense_results and sparse_results are empty"
            )

    # ── 核心方法 ──────────────────────────────────────────────

    @trace_span("retrieval", "rrf_fusion")
    def fuse(
        self,
        dense_results: list[RankedChunk],
        sparse_results: list[RankedChunk],
        top_k: int = 10,
    ) -> list[RankedChunk]:
        """执行 RRF 融合。

        Args:
            dense_results: 稠密检索结果（按 score 降序）。
            sparse_results: 稀疏检索结果（按 score 降序）。
            top_k: 返回的最大结果数。

        Returns:
            融合后按 RRF 分数降序排列的 RankedChunk 列表。

        Raises:
            RRFFusionError: 两路结果均为空。
        """
        self._validate_inputs(dense_results, sparse_results)

        # 按 chunk_id 索引
        chunk_map: dict[str, RankedChunk] = {}

        # 稠密结果排名（从 1 开始）
        for rank, chunk in enumerate(dense_results, start=1):
            if chunk.chunk_id in chunk_map:
                existing = chunk_map[chunk.chunk_id]
                existing.dense_score = chunk.dense_score
                existing.fusion_score += 1.0 / (self._rrf_k + rank)
            else:
                chunk.fusion_score = 1.0 / (self._rrf_k + rank)
                chunk_map[chunk.chunk_id] = chunk

        # 稀疏结果排名
        for rank, chunk in enumerate(sparse_results, start=1):
            if chunk.chunk_id in chunk_map:
                existing = chunk_map[chunk.chunk_id]
                existing.sparse_score = chunk.sparse_score
                existing.fusion_score += 1.0 / (self._rrf_k + rank)
            else:
                chunk.fusion_score = 1.0 / (self._rrf_k + rank)
                chunk_map[chunk.chunk_id] = chunk

        # 按融合分数从高到低排序
        fused = sorted(
            chunk_map.values(),
            key=lambda c: c.fusion_score,
            reverse=True,
        )

        # 回填 score 字段
        for chunk in fused:
            chunk.score = chunk.fusion_score

        result = fused[:top_k]

        logger.info(
            "rrf_fusion_done",
            event_type="retrieval",
            metadata={
                "dense_input": len(dense_results),
                "sparse_input": len(sparse_results),
                "unique_before_fusion": len(chunk_map),
                "final_top_k": len(result),
            },
        )

        return result


__all__ = ["RRFFusion", "RRFFusionError"]
