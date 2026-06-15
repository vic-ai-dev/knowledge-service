"""D2 — DenseRetriever：稠密向量检索。

执行步骤：
  1. 使用 EmbeddingFactory 将查询文本编码为向量
  2. 通过 VectorStoreFactory 创建 PGVectorStore
  3. 调用 pgvector.query() 检索语义相似分块
  4. 将 ``VectorSearchResult`` 转换为检索层类型
"""

from __future__ import annotations

import time
from typing import Any

from app.core.query_engine.query_types import RankedChunk
from app.libs.base.base_vector_store import BaseVectorStore
from app.libs.factory import EmbeddingFactory, VectorStoreFactory
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class DenseRetrieverError(RuntimeError):
    """DenseRetriever 通用异常。"""
    pass


class DenseRetriever:
    """稠密向量检索器。

    通过 Embedding 模型编码查询，在 pgvector 中执行余弦相似度搜索。

    :param vector_store: BaseVectorStore 实例（默认通过工厂创建）。
    :param top_k_factor: 稠密检索的召回倍数（最终 top_k * factor）。
    """

    def __init__(
        self,
        vector_store: BaseVectorStore | None = None,
        top_k_factor: int = 2,
    ):
        self._vector_store = vector_store or VectorStoreFactory.create()
        self._top_k_factor = top_k_factor
        self._embedding = None

    # ── 延迟初始化 ──────────────────────────────────────────

    def _get_embedding(self):
        if self._embedding is None:
            self._embedding = EmbeddingFactory.create()
        return self._embedding

    # ── 输入校验 ──────────────────────────────────────────────

    def _validate_query(self, query_text: str) -> None:
        if not query_text or not query_text.strip():
            raise DenseRetrieverError("query_text cannot be empty")

    # ── 核心方法 ──────────────────────────────────────────────

    @trace_span("retrieval", "dense_retrieve")
    async def retrieve(
        self,
        query_text: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RankedChunk]:
        """执行稠密语义检索。

        Args:
            query_text: 用户查询文本。
            top_k: 返回的最大结果数。
            filters: 过滤条件（category / language / doc_type 等）。

        Returns:
            按余弦相似度降序排列的 RankedChunk 列表。

        Raises:
            DenseRetrieverError: 编码或检索过程出错。
        """
        self._validate_query(query_text)
        t0 = time.monotonic()

        # 1. 编码查询
        embedder = self._get_embedding()
        try:
            query_vector = await embedder.embed_query(query_text)
        except Exception as e:
            raise DenseRetrieverError(
                f"query embedding failed: {e}"
            ) from e

        # 2. 向量检索（召回更多候选供后续排序）
        recall_k = top_k * self._top_k_factor
        try:
            results = await self._vector_store.query(
                embedding=query_vector,
                top_k=recall_k,
                filters=filters,
            )
        except Exception as e:
            raise DenseRetrieverError(
                f"vector store query failed: {e}"
            ) from e

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

        chunks = [
            RankedChunk(
                chunk_id=r.chunk_id,
                text=r.text,
                metadata=r.metadata,
                dense_score=r.score,
                score=r.score,
                source_path=r.source_path,
            )
            for r in results
        ]

        logger.info(
            "dense_retrieve_done",
            event_type="retrieval",
            metadata={
                "top_k": top_k,
                "recall_k": recall_k,
                "results": len(chunks),
                "latency_ms": elapsed_ms,
            },
        )

        return chunks


__all__ = ["DenseRetriever", "DenseRetrieverError"]
