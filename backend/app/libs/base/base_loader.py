"""Loader 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoadResult:
    text: str
    metadata: dict
    source_path: str


class BaseLoader(ABC):
    """文档加载抽象基类。"""

    @abstractmethod
    async def load(self, path: str | Path, **kwargs) -> list[LoadResult]:
        """加载文档，返回文本块及其元数据。"""
        ...
