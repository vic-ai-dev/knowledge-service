"""LLM API 调用日志辅助工具。"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from app.common.log import get_logger

_F = TypeVar("_F", bound=Callable[..., Any])
logger = get_logger("knowledge_service.instrumentation")


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
    "log_llm_call",
]
