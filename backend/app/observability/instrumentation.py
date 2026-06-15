"""全链路打点辅助工具。

提供装饰器、上下文管理器和快捷函数，方便在 Ingestion/Query Pipeline
以及服务层各阶段打点。所有打点自动继承当前 TraceContext。

核心概念：
  - trace_span: 异步函数装饰器，自动记录 span 开始/结束/异常
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from app.common.log import get_logger

_F = TypeVar("_F", bound=Callable[..., Any])
logger = get_logger("knowledge_service.instrumentation")


def trace_span(
    span_name: str | None = None,
    **fixed_metadata: Any,
) -> Callable[[_F], _F]:
    """异步函数追踪跨度装饰器。

    自动记录 span_start / span_end / span_error 事件，
    包含 span_name、耗时和结果摘要。

    用法:
        @trace_span("dense_search", top_k=10)
        async def dense_search(query: str) -> list[Chunk]:
            ...
    """

    def decorator(func: _F) -> _F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from app.core.trace import span, generate_id

            name = span_name or func.__name__
            span_id = generate_id()

            start = time.monotonic()
            logger.info(
                "span_start",
                metadata={
                    "span_name": name,
                    "span_id": span_id,
                    **fixed_metadata,
                    **kwargs,
                },
            )

            try:
                with span(name=name):
                    result = await func(*args, **kwargs)

                elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                result_summary = _summarize(result)
                logger.info(
                    "span_end",
                    metadata={
                        "span_name": name,
                        "span_id": span_id,
                        "duration_ms": elapsed_ms,
                        "result": result_summary,
                        **fixed_metadata,
                    },
                )
                return result

            except Exception as e:
                elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                logger.error(
                    "span_error",
                    error=str(e),
                    metadata={
                        "span_name": name,
                        "span_id": span_id,
                        "duration_ms": elapsed_ms,
                        **fixed_metadata,
                    },
                )
                raise

        return async_wrapper  # type: ignore[return-value]

    return decorator


def _summarize(obj: Any, max_len: int = 200) -> str:
    """截断摘要（避免日志过大）。"""
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def log_llm_call(
    model: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """记录 LLM API 调用事件（用量、模型、提供方）。

    被 openai / ollama / deepseek 等 provider 在每次 _call_api 成功后调用。
    """
    logger.info(
        "llm_call",
        metadata={
            "model": model,
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": (prompt_tokens or 0) + (completion_tokens or 0),
            },
            **(metadata or {}),
        },
    )


__all__ = [
    "trace_span",
    "log_llm_call",
]
