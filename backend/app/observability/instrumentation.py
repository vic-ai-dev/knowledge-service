"""全链路打点辅助工具。

提供装饰器、上下文管理器和快捷函数，方便在 Ingestion/Query Pipeline
以及服务层各阶段打点。所有打点自动继承当前 TraceContext。

核心概念：
  - trace_span: 异步函数装饰器，自动记录 span 开始/结束/异常
  - log_* 快捷函数：为特定 event_type 提供类型安全的日志辅助
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from app.common.log import get_logger

_F = TypeVar("_F", bound=Callable[..., Any])
logger = get_logger("knowledge_service.instrumentation")


def trace_span(
    event_type: str,
    span_name: str | None = None,
    **fixed_metadata: Any,
) -> Callable[[_F], _F]:
    """异步函数追踪跨度装饰器。

    自动记录：
      1. span_start 事件 — 包含 event_type + span_name + 参数
      2. span_end 事件 — 包含耗时 + 结果摘要
      3. span_error 事件 — 包含异常信息

    用法:
        @trace_span("retrieval", "dense_search", top_k=10)
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
                event_type=event_type,
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
                    event_type=event_type,
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
                    event_type="error",
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


# ── 快捷日志函数 ────────────────────────────────────────


def log_llm_call(
    model: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """记录 LLM 调用事件。"""
    info = {
        "model": model,
        "latency_ms": latency_ms,
        **(metadata or {}),
    }
    if prompt_tokens is not None:
        info["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        info["completion_tokens"] = completion_tokens

    logger.info("llm_call", event_type="llm_call", metadata=info)


def log_retrieval(
    retrieval_type: str,  # "dense" | "sparse" | "hybrid"
    top_k: int,
    result_count: int,
    latency_ms: float | None = None,
    filters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """记录检索事件。"""
    logger.info(
        "retrieval",
        event_type="retrieval",
        metadata={
            "retrieval_type": retrieval_type,
            "top_k": top_k,
            "result_count": result_count,
            "latency_ms": latency_ms,
            "filters": filters or {},
            **(metadata or {}),
        },
    )


def _summarize(obj: Any, max_len: int = 200) -> str:
    """截断摘要（避免日志过大）。"""
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


__all__ = [
    "trace_span",
    "log_llm_call",
    "log_retrieval",
]
