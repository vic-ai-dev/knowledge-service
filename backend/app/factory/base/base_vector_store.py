"""VectorStore 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VectorSearchResult:
    chunk_id: str
    text: str
    metadata: dict
    score: float
    source_path: str | None = None


class BaseVectorStore(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    async def upsert(self, chunks: list[dict]) -> int:
        """批量写入/更新向量。返回成功数。"""
        ...

    @abstractmethod
    async def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
        **kwargs,
    ) -> list[VectorSearchResult]:
        """向量相似度检索。"""
        ...

    @abstractmethod
    async def delete(self, chunk_ids: list[str]) -> int:
        """按 chunk_id 删除向量。返回删除数。"""
        ...

    @abstractmethod
    async def delete_by_doc_id(self, doc_id: str) -> int:
        """按文档 ID 批量删除。返回删除数。"""
        ...
