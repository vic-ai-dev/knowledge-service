"""DeepSeek LLM 实现。

DeepSeek API 兼容 OpenAI 格式，但有如下扩展：

1. **Usage 扩展** — ``prompt_cache_hit_tokens`` / ``prompt_cache_miss_tokens``
   用于统计上下文缓存命中/未命中 token 数。
2. **reasoning_content** — DeepSeek-R1 等模型返回的思考过程，
   位于 ``response.choices[0].message.reasoning_content``。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncClient

from app.libs.base.base_llm import BaseLLM, LLMResponse

DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekLLM(BaseLLM):
    """基于 DeepSeek API 的 LLM 实现。

    特性：
    - 支持 ``prompt_cache_hit_tokens`` / ``prompt_cache_miss_tokens``
    - 支持 ``reasoning_content``（思考过程提取）
    - 默认 base_url = https://api.deepseek.com
    - 默认从 ``DEEPSEEK_API_KEY`` 环境变量读取 API Key

    :param model: 模型名称（如 deepseek-v4-flash, deepseek-reasoner）。
    :param kwargs: 可包含 api_key, base_url, temperature, max_tokens 等。
    """

    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)
        self._client: AsyncClient | None = None
        self._temperature = kwargs.get("temperature", 0.0)
        self._max_tokens = kwargs.get("max_tokens", 4096)
        self._api_key = kwargs.get("api_key")
        self._base_url = kwargs.get("base_url", DEEPSEEK_DEFAULT_BASE_URL)

    # ── 延迟初始化 ──────────────────────────────────────────

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            api_key = self._api_key
            if not api_key:
                import os
                api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            import httpx
            # 系统 ALL_PROXY=socks5://... env var 会导致 httpx 被 socksio 依赖阻塞
            # 使用 trust_env=False 跳过环境变量代理检测
            self._client = AsyncClient(
                api_key=api_key or "",
                base_url=self._base_url,
                http_client=httpx.AsyncClient(trust_env=False),
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
        message = choice.message
        content = message.content or ""

        # DeepSeek 特有：reasoning_content（思考过程）
        reasoning_content = getattr(message, "reasoning_content", None)

        # DeepSeek 特有 usage 扩展
        usage = response.usage.model_dump() if response.usage else None

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
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
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def count_tokens(self, text: str) -> int:
        """使用近似算法估算 Token 数量。"""
        import re

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_chars = len(text) - chinese_chars
        return int(ascii_chars / 4 + chinese_chars / 1.5) + 1
