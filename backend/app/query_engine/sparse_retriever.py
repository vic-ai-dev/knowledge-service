"""D3 — SparseRetriever：BM25 稀疏检索（local 内存版）。

封装 BM25Indexer，将 local 内存检索结果转换为统一的
RankedChunk 格式，用于后续 RRF 融合。
"""

from __future__ import annotations

import time
from typing import Any

from app.query_engine.query_types import RankedChunk
from app.ingestion.storage.bm25_indexer import BM25Indexer
from app.common.log import get_logger

logger = get_logger(__name__)

class SparseRetrieverError(RuntimeError):
    """SparseRetriever 通用异常。"""
    pass

class SparseRetriever:
    """BM25 稀疏检索器。

    基于 local（Python 内存库）+ jieba 分词，适合中英文混合的精确匹配和关键词搜索。

    :param bm25_indexer: BM25Indexer 实例（默认从配置创建）。
    """

    def __init__(self, bm25_indexer: BM25Indexer | None = None):
        if bm25_indexer is not None:
            self._indexer = bm25_indexer
        else:
            self._indexer = BM25Indexer()

    # ── 输入校验 ──────────────────────────────────────────────

    def _validate_query(self, query_text: str) -> None:
        if not query_text or not query_text.strip():
            raise SparseRetrieverError("query_text cannot be empty")

    # ── 核心方法 ──────────────────────────────────────────────
    async def retrieve(
        self,
        query_text: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RankedChunk]:
        """执行 BM25 全文检索。

        Args:
            query_text: 用户查询文本。
            top_k: 返回的最大结果数。
            filters: 过滤条件。

        Returns:
            按 BM25 相关性降序排列的 RankedChunk 列表。

        Raises:
            SparseRetrieverError: 检索过程出错。
        """
        self._validate_query(query_text)
        t0 = time.monotonic()

        try:
            results = await self._indexer.search(
                query=query_text,
                top_k=top_k,
                filters=filters,
            )
        except Exception as e:
            raise SparseRetrieverError(
                f"BM25 search failed: {e}"
            ) from e

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

        chunks = [
            RankedChunk(
                chunk_id=r.chunk_id,
                text=r.text,
                metadata=r.metadata,
                sparse_score=r.score,
                score=r.score,
                title=r.source_path,
                doc_id=r.doc_id,
                category=r.category,
                language=r.language,
                doc_type=r.doc_type,
            )
            for r in results
        ]

        logger.info(
            "sparse_retrieve_done",
            metadata={
                "top_k": top_k,
                "results": len(chunks),
                "latency_ms": elapsed_ms,
            },
        )

        return chunks

__all__ = ["SparseRetriever", "SparseRetrieverError"]
