"""控制台渲染器 — 方括号格式输出，支持颜色与堆栈追踪。"""

from __future__ import annotations

import logging
from typing import Any


# ── ANSI 颜色常量 ───────────────────────────────────────

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",       # 青色
    "INFO": "\033[32m",        # 绿色
    "WARNING": "\033[33m",     # 黄色
    "ERROR": "\033[31m",       # 红色
    "CRITICAL": "\033[31;1m",  # 亮红粗体
}
_RESET = "\033[0m"
_DIM = "\033[2m"


# ── 工具函数 ─────────────────────────────────────────────


def abbreviate_classname(name: str) -> str:
    """Spring Boot 风格类名缩写。

    "app.api.documents"   -> "a.a.documents"
    "app.observability"   -> "a.observability"
    "app.main"            -> "a.main"
    """
    if not name or name == "-":
        return "-"
    parts = name.split(".")
    if len(parts) <= 2:
        return name
    return ".".join(p[0] for p in parts[:-1] if p) + "." + parts[-1]


# ── BracketConsoleRenderer ──────────────────────────────


class BracketConsoleRenderer:
    """structlog 控制台渲染器 — 方括号格式 + 堆栈追踪。

    输出格式:
      [2025-06-15T10:30:00.123456Z] [INFO   ] [a.a.documents] [abc12345] [def67890] [req-uuid-123] 消息  key=val ...

    异常堆栈以缩进块追加在日志行末尾，ERROR/CRITICAL 级别堆栈用红色高亮。
    """

    def __call__(
        self,
        _logger: logging.Logger,
        _method_name: str,
        event_dict: dict[str, Any],
    ) -> str:
        # -- timestamp --
        ts = event_dict.pop("timestamp", "-")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        elif not isinstance(ts, str):
            ts = str(ts)
        if "T" not in ts:
            ts = "-"

        # -- level --
        raw_level = event_dict.pop("level", "INFO")
        if isinstance(raw_level, int):
            raw_level = logging.getLevelName(raw_level)
        level = str(raw_level).upper()

        # -- logger name (Spring Boot 风格缩写) --
        logger_name = event_dict.pop("_logger_name", "-")
        name_s = abbreviate_classname(logger_name)

        # -- trace / span / request IDs --
        trace_id = event_dict.pop("trace_id", "") or ""
        span_id = event_dict.pop("span_id", "") or ""
        request_id = event_dict.pop("request_id", "") or ""

        event = event_dict.pop("event", "")
        exception = event_dict.pop("exception", None)

        # -- 移除内部元字段 --
        for _k in ("_record", "_from_structlog", "service", "parent_span_id"):
            event_dict.pop(_k, None)

        # -- 截断 ID 显示 --
        trace_s = trace_id[:12] if trace_id else "-"
        span_s = span_id[:12] if span_id else "-"
        req_s = request_id[:16] if request_id else "-"

        # -- 构建固定字段前缀 --
        level_color = _LEVEL_COLORS.get(level, "")
        if level_color:
            colored_level = f"{level_color}{level:<7}{_RESET}"
        else:
            colored_level = f"{level:<7}"
        line = (
            f"[{ts}] "
            f"[{colored_level}] "
            f"[{name_s}] "
            f"[{trace_s}] "
            f"[{span_s}] "
            f"[{req_s}] "
            f"{event}"
        )

        # -- 剩余业务字段 --
        if event_dict:
            extra = "  " + "  ".join(
                f"{_DIM}{k}={v}{_RESET}"
                if isinstance(v, (int, float))
                else f"{k}={v}"
                for k, v in event_dict.items()
            )
            line += extra

        # -- 异常堆栈 --
        if exception:
            line += f"\n{_LEVEL_COLORS.get('ERROR', '')}{exception.rstrip(chr(10))}{_RESET}"

        return line


__all__ = [
    "abbreviate_classname",
    "BracketConsoleRenderer",
]
