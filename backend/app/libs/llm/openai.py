"""OpenAI-compatible LLM 实现。

支持 OpenAI、Azure OpenAI、DeepSeek 等所有 OpenAI-compatible 后端。
通过 ``base_url`` 区分不同提供商。
Client 延迟初始化，避免在单元测试中因系统代理配置导致 ImportError。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncClient

from app.libs.base.base_llm import BaseLLM, LLMResponse


class OpenAILLM(BaseLLM):
    """基于 OpenAI-compatible API 的 LLM 实现。

    :param model: 模型名称（如 gpt-4o, deepseek-v4-flash）。
    :param kwargs: 可包含 api_key, base_url, temperature, max_tokens 等。
    """

    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)
        self._client: AsyncClient | None = None
        self._temperature = kwargs.get("temperature", 0.0)
        self._max_tokens = kwargs.get("max_tokens", 4096)
        self._api_key = kwargs.get("api_key")
        self._base_url = kwargs.get("base_url")

    # ── 延迟初始化 ──────────────────────────────────────────

    def _get_client(self) -> AsyncClient:
        """延迟创建 AsyncClient，避免构造时因系统代理触发 ImportError。"""
        if self._client is None:
            api_key = self._api_key
            if not api_key:
                import os
                api_key = os.environ.get("OPENAI_API_KEY", "")

            self._client = AsyncClient(
                api_key=api_key or "",
                base_url=self._base_url,
            )
        return self._client

    # ── BaseLLM 接口实现 ──────────────────────────────────────

    async def generate(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        msgs = self._build_messages(prompt, messages)
        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            stream=False,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None,
            finish_reason=choice.finish_reason,
        )

    async def generate_stream(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        msgs = self._build_messages(prompt, messages)
        client = self._get_client()

        stream = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def count_tokens(self, text: str) -> int:
        """使用近似算法估算 Token 数量。

        英文约 4 字符/token，中文约 1.5 字符/token。
        """
        import re

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_chars = len(text) - chinese_chars

        return int(ascii_chars / 4 + chinese_chars / 1.5) + 1
