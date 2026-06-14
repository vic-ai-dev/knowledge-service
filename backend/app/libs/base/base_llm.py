"""LLM 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


class BaseLLM(ABC):
    """LLM 抽象基类。"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """同步生成回答。"""
        ...

    @abstractmethod
    async def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式生成回答。"""
        ...
        yield  # pragma: no cover

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """估算 Token 数量。"""
        ...
