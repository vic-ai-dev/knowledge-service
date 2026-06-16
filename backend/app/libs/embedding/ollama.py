"""Ollama Embedding 实现。

Ollama 提供 OpenAI-compatible 的 Embedding API（/v1/embeddings）。
使用与 OpenAIEmbedding 相同的 API 调用，但默认参数不同。
"""

from __future__ import annotations

from typing import Any

from openai import AsyncClient

from app.libs.base.base_embedding import BaseEmbedding, EmbeddingResult
from app.common.log import get_logger

import openai
from app.libs.embedding.openai import EmbeddingError

logger = get_logger(__name__)

OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"

class OllamaEmbedding(BaseEmbedding):
    """基于 Ollama 的 Embedding 实现。

    :param model: 模型名称（如 qwen3-embedding:0.6b）。
    :param kwargs: 可包含 api_key, base_url, dimensions 等。
    """

    def __init__(self, model: str, **kwargs: Any):
        super().__init__()
        self._model = model
        self._api_key = kwargs.get("api_key", "ollama")
        self._base_url = kwargs.get("base_url", OLLAMA_DEFAULT_BASE_URL)
        self._dimensions = kwargs.get("dimensions", 1536)
        self._client: AsyncClient | None = None

    # ── 延迟初始化 ──

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            import httpx
            self._client = AsyncClient(
                api_key=self._api_key,
                base_url=self._base_url,
                http_client=httpx.AsyncClient(trust_env=False),
            )
        return self._client

    # ── API 调用层（分离以支持 mock） ──

    async def _call_api(self, model: str, input_texts: str | list[str]) -> Any:
        """执行实际 API 调用，附带完善的错误处理。"""
        client = self._get_client()
        try:
            return await client.embeddings.create(
                model=model,
                input=input_texts,
            )
        except openai.APIStatusError as e:
            error_detail = self._parse_error_response(e)
            raise EmbeddingError(
                f"[OllamaEmbedding] API error (HTTP {e.status_code}): {error_detail}"
            ) from e
        except openai.APITimeoutError as e:
            raise EmbeddingError("[OllamaEmbedding] Request timed out") from e
        except openai.APIConnectionError as e:
            raise EmbeddingError(
                f"[OllamaEmbedding] Connection failed: {e}"
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

    # ── 输入校验 ──

    def _validate_texts(self, texts: list[str]) -> None:
        if not texts:
            raise EmbeddingError("texts list cannot be empty")

    def _validate_query(self, text: str) -> None:
        if not text or not text.strip():
            raise EmbeddingError("query text cannot be empty")

    # ── BaseEmbedding 接口实现 ──
    async def embed_documents(
        self, texts: list[str], **kwargs: Any
    ) -> EmbeddingResult:
        self._validate_texts(texts)
        response = await self._call_api(self._model, texts)
        vectors = [d.embedding for d in response.data]
        total_tokens = response.usage.total_tokens if response.usage else 0
        return EmbeddingResult(
            vectors=vectors,
            model=response.model,
            total_tokens=total_tokens,
        )
    async def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        self._validate_query(text)
        response = await self._call_api(self._model, text)
        return response.data[0].embedding

    @property
    def dimensions(self) -> int:
        return self._dimensions
