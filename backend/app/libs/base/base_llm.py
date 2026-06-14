"""LLM 抽象接口。支持 prompt 和 messages 两种调用方式。"""

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
    """LLM 抽象基类。

    所有 LLM 实现必须继承此类并实现三个抽象方法。

    :param model: 模型名称。
    :param kwargs: 额外参数（会在构造时保存，子类可访问 self._kwargs）。
    """

    def __init__(self, model: str, **kwargs):
        self.model = model
        self._kwargs = kwargs

    # ── 辅助方法 ──────────────────────────────────────────────

    def _build_messages(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
    ) -> list[dict]:
        """统一构造 chat messages 格式。

        优先使用 ``messages``；退而使用 ``prompt`` 构造单条用户消息。
        如果两者都未提供则抛出 ValueError。
        """
        if messages is not None:
            return messages
        if prompt is not None:
            return [{"role": "user", "content": prompt}]
        raise ValueError("必须提供 prompt 或 messages 之一")

    # ── 抽象接口 ──────────────────────────────────────────────

    @abstractmethod
    async def generate(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """生成回答（非流式）。

        Args:
            prompt: 字符串提示（与 messages 二选一）。
            messages: Chat 消息列表（与 prompt 二选一）。
            **kwargs: 额外参数。
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成回答。

        Args:
            prompt: 字符串提示（与 messages 二选一）。
            messages: Chat 消息列表（与 prompt 二选一）。
            **kwargs: 额外参数。
        """
        ...
        yield  # pragma: no cover

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """估算 Token 数量。"""
        ...
