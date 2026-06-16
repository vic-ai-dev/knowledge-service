"""
CrossEncoder Reranker 实现。

Uses an LLM (via OpenAI-compatible API) to score query-document relevance,
then re-orders candidates by relevance score descending.

与 B1 LLM 实现保持一致的：
- _call_api 分离层（支持 mock）
- _parse_error_response 结构化错误解析
- RerankerError 自定义异常
- 输入校验
"""

from __future__ import annotations

import asyncio
from typing import Any

import openai
from openai import AsyncClient

from app.factory.base.base_reranker import BaseReranker, RerankResult
from app.common.log import get_logger

logger = get_logger(__name__)

RERANK_PROMPT_TEMPLATE = """You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.

Query: {query}

Passage: {passage}

Relevance score:"""

class RerankerError(RuntimeError):
    """Reranker 调用通用异常。"""
    pass

class CrossEncoderReranker(BaseReranker):
    """Cross-encoder style reranker using an LLM via OpenAI-compatible API.

    Each candidate is scored independently, then results are sorted
    by score descending.
    """

    def __init__(self, **kwargs: Any):
        self._model = kwargs.get("model", "dengcao/Qwen3-Reranker-0.6B:Q8_0")
        self._api_key = kwargs.get("api_key", "ollama")
        self._base_url = kwargs.get("base_url", "http://127.0.0.1:11434/v1")
        self._top_k = kwargs.get("top_k", 5)
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

    async def _call_api(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 10,
    ) -> Any:
        """执行实际 API 调用，附带完善的错误处理。

        此方法分离以便在单元测试中轻松 mock ``_call_api``，
        而不需要 mock 整个 ``AsyncClient``。
        """
        client = self._get_client()
        try:
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except openai.APIStatusError as e:
            error_detail = self._parse_error_response(e)
            raise RerankerError(
                f"[Reranker] API error (HTTP {e.status_code}): {error_detail}"
            ) from e
        except openai.APITimeoutError as e:
            raise RerankerError("[Reranker] Request timed out") from e
        except openai.APIConnectionError as e:
            raise RerankerError(
                f"[Reranker] Connection failed: {e}"
            ) from e

    def _parse_error_response(self, error: openai.APIStatusError) -> str:
        """解析 API 错误响应体，提取可读的错误信息。"""
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

    def _validate_inputs(self, query: str, candidates: list[dict]) -> None:
        if not query or not query.strip():
            raise RerankerError("query cannot be empty")
        if not candidates:
            raise RerankerError("candidates list cannot be empty")

    # ── BaseReranker 接口实现 ──
    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        self._validate_inputs(query, candidates)
        top_k = min(top_k or self._top_k, len(candidates))

        async def _score(candidate: dict) -> RerankResult:
            text = candidate.get("text", "")
            prompt = RERANK_PROMPT_TEMPLATE.format(query=query, passage=text)
            resp = await self._call_api(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
            )
            raw = resp.choices[0].message.content.strip() if resp.choices else "0"
            try:
                score = float(raw.split()[0])
            except (ValueError, IndexError):
                score = candidate.get("score", 0.0)

            return RerankResult(
                chunk_id=candidate.get("chunk_id", ""),
                text=text,
                score=score,
                metadata=candidate.get("metadata"),
            )

        scored = await asyncio.gather(*[_score(c) for c in candidates])
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
