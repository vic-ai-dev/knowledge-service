"""Ollama LLM 实现。

使用 Ollama 的 OpenAI-compatible 端点（默认 http://127.0.0.1:11434/v1）。
Client 延迟初始化，避免单元测试中因系统代理触发 ImportError。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import openai
from openai import AsyncClient

from app.libs.base.base_llm import BaseLLM, LLMResponse
from app.common.log import get_logger
from app.observability.instrumentation import trace_span, log_llm_call
from app.libs.llm.openai import LLMError

logger = get_logger(__name__)

OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"


class OllamaLLM(BaseLLM):
    """基于 Ollama 的 LLM 实现。

    :param model: 模型名称（如 qwen2.5:7b, llama3.2:3b）。
    :param kwargs: 可包含 api_key, base_url, temperature, max_tokens 等。
    """

    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)
        self._client: AsyncClient | None = None
        self._temperature = kwargs.get("temperature", 0.0)
        self._max_tokens = kwargs.get("max_tokens", 4096)
        self._api_key = kwargs.get("api_key", "ollama")
        self._base_url = kwargs.get("base_url", OLLAMA_DEFAULT_BASE_URL)

    # ── 延迟初始化 ──────────────────────────────────────────

    def _get_client(self) -> AsyncClient:
        """延迟创建 AsyncClient。"""
        if self._client is None:
            import httpx
            self._client = AsyncClient(
                api_key=self._api_key,
                base_url=self._base_url,
                http_client=httpx.AsyncClient(trust_env=False),
            )
        return self._client

    # ── API 调用层（分离以支持 mock） ──────────────────────

    async def _call_api(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
    ) -> Any:
        """执行实际 API 调用，附带完善的错误处理。"""
        client = self._get_client()
        try:
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
        except openai.APIStatusError as e:
            error_detail = self._parse_error_response(e)
            raise LLMError(
                f"[Ollama] API error (HTTP {e.status_code}): {error_detail}"
            ) from e
        except openai.APITimeoutError as e:
            raise LLMError("[Ollama] Request timed out") from e
        except openai.APIConnectionError as e:
            raise LLMError(
                f"[Ollama] Connection failed: {e}"
            ) from e

    def _parse_error_response(self, error: openai.APIStatusError) -> str:
        """解析 API 错误响应体。"""
        try:
            body = error.response.json()
            if "error" in body:
                err = body["error"]
                if isinstance(err, dict):
                    return err.get("message", str(err))
                return str(err)
            return error.response.text
        except Exception:
            return error.response.text or "Unknown error"

    # ── BaseLLM 接口实现 ──────────────────────────────────────

    @trace_span()
    async def generate(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        msgs = self._build_messages(prompt, messages)

        response = await self._call_api(
            messages=msgs,
            model=kwargs.get("model", self.model),
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
        )

        choice = response.choices[0]
        usage_dict = response.usage.model_dump() if response.usage else None
        if usage_dict:
            log_llm_call(
                self.model,
                prompt_tokens=usage_dict.get("prompt_tokens"),
                completion_tokens=usage_dict.get("completion_tokens"),
                metadata={"provider": "ollama"},
            )
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=usage_dict,
            finish_reason=choice.finish_reason,
        )

    async def generate_stream(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        msgs = self._build_messages(prompt, messages)

        stream = await self._call_api(
            messages=msgs,
            model=kwargs.get("model", self.model),
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def count_tokens(self, text: str) -> int:
        """使用近似算法估算 Token 数量。"""
        import re

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_chars = len(text) - chinese_chars

        return int(ascii_chars / 4 + chinese_chars / 1.5) + 1
