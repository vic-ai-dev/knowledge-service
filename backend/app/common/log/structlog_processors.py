"""structlog 自定义处理器链 — 日志器名称、异常、Trace/Service 上下文注入。"""

from __future__ import annotations

import logging
import sys
from typing import Any


def set_logger_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """从 _record 提取日志器全名，供 ConsoleRenderer 列使用。

    必须在 ``ProcessorFormatter`` 的处理器链中运行（在 ``remove_processors_meta`` 之前）。
    """
    record = event_dict.get("_record")
    if record is not None:
        event_dict["logger_name"] = record.name
    return event_dict


def auto_exc_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """自动捕获异常上下文中的 exc_info。

    当在 ``except`` 块内调用日志且未显式传递 ``exc_info`` 时，
    自动注入 ``exc_info=True``，使后续的 ``format_exc_info`` 处理器
    能识别并生成堆栈跟踪。

    若 ``exc_info`` 已显式设置（包括 ``False``），原值保留。
    """
    if "exc_info" not in event_dict:
        try:
            if sys.exc_info() != (None, None, None):
                event_dict["exc_info"] = True
        except Exception:
            pass
    return event_dict


def add_trace_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """注入 trace_id / span_id / request_id。"""
    from app.core.trace import get_trace_context

    event_dict.update(get_trace_context())
    return event_dict


def add_service_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """注入 service 标识。"""
    from app.core.settings import get_settings

    try:
        event_dict["service"] = get_settings().observability.logging.service_name
    except Exception:
        event_dict["service"] = "knowledge_service"
    return event_dict


__all__ = [
    "set_logger_name",
    "auto_exc_info",
    "add_trace_context",
    "add_service_name",
]
