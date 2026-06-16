"""TraceContext — 请求级上下文（仅保留 request_id）。

OpenTelemetry 已取代 trace_id/span_id 的手动管理。
request_id 仍由 FastAPI middleware 注入，用于前端日志关联。"""
from __future__ import annotations

import contextvars
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    return request_id_var.get()


def set_request_id(rid: str | None = None) -> str:
    rid = rid or str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


__all__ = [
    "get_request_id",
    "set_request_id",
    "request_id_var",
]
