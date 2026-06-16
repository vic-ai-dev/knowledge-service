"""Embedding 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    total_tokens: int = 0


class BaseEmbedding(ABC):
    """Embedding 抽象基类。"""

    @abstractmethod
    async def embed_documents(self, texts: list[str], **kwargs) -> EmbeddingResult:
        """批量文档向量化。"""
        ...

    @abstractmethod
    async def embed_query(self, text: str, **kwargs) -> list[float]:
        """单条查询向量化。"""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """返回向量维度。"""
        ...
