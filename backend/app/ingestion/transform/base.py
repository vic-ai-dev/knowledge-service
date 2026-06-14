"""Transform 基类 — 摄入管线中的 Chunk 变换步骤。

每个 Transform 接收 ChunkRecord 列表，执行单向变换（增/删/改字段），
返回新的 ChunkRecord 列表。Transform 是可组合的串联单元。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.ingestion.models import ChunkRecord


class TransformError(RuntimeError):
    """Transform 执行异常。"""
    pass


class BaseTransform(ABC):
    """Chunk 变换抽象基类。

    所有 Transform 实现必须继承此类并实现 ``transform`` 方法。
    Transform 是幂等的：给定相同的输入，应产生相同的输出。
    """

    @abstractmethod
    async def transform(
        self,
        chunks: list[ChunkRecord],
        **kwargs: Any,
    ) -> list[ChunkRecord]:
        """对 Chunk 列表执行单向变换。

        Args:
            chunks: 输入 ChunkRecord 列表。
            **kwargs: 运行时参数。

        Returns:
            变换后的 ChunkRecord 列表（数量可能减少或增加）。

        Raises:
            TransformError: 变换过程中发生不可恢复的错误。
        """
        ...

    async def __call__(
        self,
        chunks: list[ChunkRecord],
        **kwargs: Any,
    ) -> list[ChunkRecord]:
        """使 Transform 可调用。"""
        return await self.transform(chunks, **kwargs)
