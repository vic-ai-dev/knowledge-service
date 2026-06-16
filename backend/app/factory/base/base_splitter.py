"""Splitter 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SplitResult:
    text: str
    metadata: dict
    chunk_index: int


class BaseSplitter(ABC):
    """文档分块抽象基类。"""

    @abstractmethod
    def split(self, text: str, metadata: dict | None = None) -> list[SplitResult]:
        """将文本切分为 Chunks。"""
        ...

    @property
    @abstractmethod
    def chunk_size(self) -> int:
        ...

    @property
    @abstractmethod
    def chunk_overlap(self) -> int:
        ...
