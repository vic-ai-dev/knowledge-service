"""C12 — VectorUpserter：向量存储写入器。

职责：
  1. 接收 ChunkRecord 列表，转换为 dict 格式
  2. 通过 BaseVectorStore.upsert() 批量写入 pgvector
  3. 记录写入指标与异常
"""

from __future__ import annotations

from typing import Any

from app.ingestion.models import ChunkRecord
from app.libs.base.base_vector_store import BaseVectorStore
from app.libs.factory import VectorStoreFactory
from app.observability import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class VectorUpserterError(RuntimeError):
    """VectorUpserter 通用异常。"""
    pass


class VectorUpserter:
    """向量存储写入器。

    将 ChunkRecord 列表写入 pgvector，支持增量 upsert。

    :param vector_store: BaseVectorStore 实例（默认通过工厂创建）。
    :param kwargs: 传递给 VectorStoreFactory.create() 的参数。
    """

    def __init__(
        self,
        vector_store: BaseVectorStore | None = None,
        **kwargs: Any,
    ):
        if vector_store is not None:
            self._store = vector_store
        else:
            self._store = VectorStoreFactory.create(**kwargs)

    # ── 输入校验 ──

    def _validate_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            raise VectorUpserterError("chunks list cannot be empty")

    # ── ChunkRecord → dict 转换 ──

    @staticmethod
    def _chunk_to_dict(chunk: ChunkRecord) -> dict:
        """将 ChunkRecord 转换为存储层所需的 dict 格式。

        跳过 embedding 为 None 的 Chunk。
        """
        if chunk.embedding is None:
            raise VectorUpserterError(
                f"chunk {chunk.chunk_id} has no embedding, encode first"
            )

        return {
            "id": chunk.chunk_id,
            "text": chunk.text,
            "metadata": chunk.metadata,
            "collection": chunk.collection,
            "category": chunk.category,
            "language": chunk.language,
            "doc_type": chunk.doc_type,
            "doc_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "source_path": chunk.source_path,
            "token_count": chunk.token_count,
            "embedding": chunk.embedding,
        }

    # ── 核心方法 ──

    @trace_span("indexing", "vector_upsert")
    async def upsert(self, chunks: list[ChunkRecord]) -> int:
        """批量写入 ChunkRecord 到 pgvector。

        Args:
            chunks: 已编码的 ChunkRecord 列表（必须有 embedding）。

        Returns:
            成功写入的 Chunk 数量。

        Raises:
            VectorUpserterError: 输入为空或写入失败。
        """
        self._validate_chunks(chunks)

        # 过滤无 embedding 的 Chunk
        valid_docs: list[dict] = []
        skipped = 0
        for chunk in chunks:
            try:
                valid_docs.append(self._chunk_to_dict(chunk))
            except VectorUpserterError:
                skipped += 1

        if not valid_docs:
            logger.warning(
                "vector_upsert_skip_all",
                event_type="indexing",
                metadata={"total": len(chunks), "skipped": skipped},
            )
            return 0

        count = await self._store.upsert(valid_docs)

        logger.info(
            "vector_upsert_done",
            event_type="indexing",
            metadata={
                "total_input": len(chunks),
                "upserted": count,
                "skipped": skipped,
            },
        )

        return count

    @trace_span("indexing", "vector_delete_by_doc_id")
    async def delete_by_doc_id(self, doc_id: str) -> int:
        """按文档 ID 删除向量。

        Args:
            doc_id: 文档 UUID。

        Returns:
            删除的记录数。
        """
        count = await self._store.delete_by_doc_id(doc_id)
        logger.info(
            "vector_delete_by_doc_id",
            event_type="indexing",
            metadata={"doc_id": doc_id, "deleted": count},
        )
        return count


__all__ = ["VectorUpserter", "VectorUpserterError"]
