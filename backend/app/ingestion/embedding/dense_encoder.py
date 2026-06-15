"""C8 — DenseEncoder：稠密向量编码器。

职责：
  1. 对 ChunkRecord 列表中的文本进行批量 Embedding
  2. 将生成的向量回填到 ChunkRecord.embedding 字段
  3. 使用 EmbeddingFactory 创建底层 Embedding 实例
"""

from __future__ import annotations

from typing import Any

from app.ingestion.models import ChunkRecord
from app.libs.base.base_embedding import EmbeddingResult
from app.libs.factory import EmbeddingFactory
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


class DenseEncodeError(RuntimeError):
    """DenseEncoder 通用异常。"""
    pass


class DenseEncoder:
    """稠密向量编码器。

    通过 EmbeddingFactory 获取 Embedding 实例，对 ChunkRecord
    列表执行批量 Embedding。

    :param batch_size: 单次 Embedding API 调用的最大文本数。
    :param provider: Embedding provider（None 则使用配置默认值）。
    :param model: Embedding 模型名称（None 则使用配置默认值）。
    """

    def __init__(
        self,
        batch_size: int = 32,
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ):
        if batch_size < 1:
            raise DenseEncodeError(f"batch_size must be >= 1, got {batch_size}")
        self._batch_size = batch_size
        self._provider = provider
        self._model = model
        self._kwargs = kwargs
        self._embedding = None

    # ── 延迟初始化 ──

    def _get_embedding(self):
        """获取或创建 Embedding 实例。"""
        if self._embedding is None:
            self._embedding = EmbeddingFactory.create(
                provider=self._provider,
                model=self._model,
                **self._kwargs,
            )
        return self._embedding

    # ── 输入校验 ──

    def _validate_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            raise DenseEncodeError("chunks list cannot be empty")

    # ── 核心方法 ──

    @trace_span("embedding", "dense_encode")
    async def encode(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        """对 ChunkRecord 列表执行批量 Embedding。

        Args:
            chunks: 输入 ChunkRecord 列表。

        Returns:
            嵌入向量后的 ChunkRecord 列表（修改原对象并返回）。

        Raises:
            DenseEncodeError: Embedding 过程中发生错误。
        """
        if not chunks:
            return chunks

        self._validate_chunks(chunks)
        embedder = self._get_embedding()
        texts = [chunk.text for chunk in chunks]
        total = len(texts)

        # 分批处理
        for start in range(0, total, self._batch_size):
            end = min(start + self._batch_size, total)
            batch = texts[start:end]

            try:
                result: EmbeddingResult = await embedder.embed_documents(batch)
            except Exception as e:
                raise DenseEncodeError(
                    f"Batch embedding failed at offset {start}: {e}"
                ) from e

            for j, vector in enumerate(result.vectors):
                chunks[start + j].embedding = vector

            logger.info(
                "dense_encode_batch",
                event_type="embedding",
                metadata={
                    "batch_start": start,
                    "batch_size": len(batch),
                    "total_chunks": total,
                    "completed": min(end, total),
                    "model": result.model,
                },
            )

        logger.info(
            "dense_encode_complete",
            event_type="embedding",
            metadata={"total_chunks": total},
        )

        return chunks


__all__ = ["DenseEncoder", "DenseEncodeError"]
