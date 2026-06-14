"""TraceContext — 分布式追踪上下文管理器。

使用 contextvars 实现协程安全的上下文传播。
每个请求/任务创建一个追踪上下文，通过 span() 创建子跨度。

用法:
    with trace_context() as ctx:
        logger.info("operation", trace_id=ctx["trace_id"])
        with span(name="sub_task") as child_ctx:
            logger.info("sub operation")
"""

from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from typing import Generator

# ── contextvars（协程安全） ─────────────────────────────

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")
parent_span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("parent_span_id", default="")
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


# ── Getter ──────────────────────────────────────────────


def get_trace_id() -> str:
    return trace_id_var.get()


def get_span_id() -> str:
    return span_id_var.get()


def get_parent_span_id() -> str:
    return parent_span_id_var.get()


def get_request_id() -> str:
    return request_id_var.get()


def get_trace_context() -> dict[str, str]:
    """获取当前追踪上下文字典（字段为空时排除）。"""
    ctx: dict[str, str] = {}
    if tid := get_trace_id():
        ctx["trace_id"] = tid
    if sid := get_span_id():
        ctx["span_id"] = sid
    if pid := get_parent_span_id():
        ctx["parent_span_id"] = pid
    if rid := get_request_id():
        ctx["request_id"] = rid
    return ctx


def generate_id() -> str:
    """生成 UUID v4 字符串。"""
    return str(uuid.uuid4())


def generate_short_id() -> str:
    """生成短 ID（8 位十六进制）。"""
    return uuid.uuid4().hex[:8]


# ── 上下文管理器 ────────────────────────────────────────


@contextmanager
def trace_context(
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    request_id: str | None = None,
) -> Generator[dict[str, str], None, None]:
    """创建顶层追踪上下文。

    通常在请求入口调用；如果没有 trace_id 则自动生成。
    如果已有上下文则原样套用（跨服务传播）。
    """
    new_trace_id = trace_id or get_trace_id() or generate_id()
    new_span_id = span_id or generate_id()
    new_parent_span_id = parent_span_id or get_parent_span_id() or ""
    new_request_id = request_id or get_request_id() or ""

    token_t = trace_id_var.set(new_trace_id)
    token_s = span_id_var.set(new_span_id)
    token_p = parent_span_id_var.set(new_parent_span_id)
    token_r = request_id_var.set(new_request_id)

    ctx = {
        "trace_id": new_trace_id,
        "span_id": new_span_id,
        "parent_span_id": new_parent_span_id,
        "request_id": new_request_id,
    }

    try:
        yield ctx
    finally:
        trace_id_var.reset(token_t)
        span_id_var.reset(token_s)
        parent_span_id_var.reset(token_p)
        request_id_var.reset(token_r)


@contextmanager
def span(name: str = "") -> Generator[dict[str, str], None, None]:
    """在当前追踪上下文中创建一个子 span。

    保留 trace_id，当前 span_id 升为 parent_span_id，新生成 span_id。
    """
    current_trace_id = get_trace_id()
    if not current_trace_id:
        with trace_context() as ctx:
            yield ctx
        return

    current_span_id = get_span_id()
    new_span_id = generate_id()

    token_s = span_id_var.set(new_span_id)
    token_p = parent_span_id_var.set(current_span_id)

    ctx: dict[str, str] = {
        "trace_id": current_trace_id,
        "span_id": new_span_id,
        "parent_span_id": current_span_id or "",
    }
    if name:
        ctx["span_name"] = name

    try:
        yield ctx
    finally:
        span_id_var.reset(token_s)
        parent_span_id_var.reset(token_p)


__all__ = [
    "get_trace_id",
    "get_span_id",
    "get_parent_span_id",
    "get_request_id",
    "get_trace_context",
    "generate_id",
    "generate_short_id",
    "trace_context",
    "span",
]
