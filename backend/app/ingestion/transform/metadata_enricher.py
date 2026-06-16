"""C6 — MetadataEnricher：为 Chunk 注入文档级元数据。

职责：
  1. 将文档级元数据（category, language, doc_type, source_path 等）
     注入到每个 ChunkRecord 中
  2. 添加处理时间戳、版本号等运维元数据
  3. 保留 Chunk 级已有的元数据（不覆盖同名键）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.ingestion.models import ChunkRecord
from app.ingestion.transform.base import BaseTransform


class MetadataEnricher(BaseTransform):
    """为 Chunk 注入文档级元数据。

    :param document_meta: 文档级元数据字典。
        包含 category, language, doc_type, source_path, collection 等。
    :param defaults: 默认元数据（当 document_meta 未提供时使用）。
    """

    def __init__(
        self,
        document_meta: dict[str, Any] | None = None,
        **defaults: Any,
    ):
        self._document_meta = document_meta or {}
        self._defaults = {
            "enrich_version": "1.0",
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            **defaults,
        }

    async def transform(
        self,
        chunks: list[ChunkRecord],
        **kwargs: Any,
    ) -> list[ChunkRecord]:
        """为每个 Chunk 注入元数据。

        优先级（从高到低）：
          1. Chunk 已有字段（不覆盖）
          2. document_meta（运行时注入）
          3. defaults（构造时默认值）
        """
        if not chunks:
            return chunks

        doc_meta = kwargs.get("document_meta", self._document_meta)

        for chunk in chunks:
            # 文档级元数据（不覆盖 Chunk 已有值）
            for key, value in doc_meta.items():
                if hasattr(chunk, key) and getattr(chunk, key) is None:
                    setattr(chunk, key, value)
                elif key not in chunk.metadata:
                    chunk.metadata[key] = value

            # 默认值（不覆盖已有）
            for key, value in self._defaults.items():
                if key not in chunk.metadata:
                    chunk.metadata[key] = value

            # 确保 chunk_id 存在
            if not chunk.id:
                chunk.id = str(uuid.uuid4())

        return chunks
