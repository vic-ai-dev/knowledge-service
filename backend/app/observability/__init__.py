"""可观测性基础设施 — structlog 结构化日志。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog


# ── 字段颜色映射（终端 ANSI） ─────────────────────────────

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


def _abbreviate_classname(name: str) -> str:
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
        name_s = _abbreviate_classname(logger_name)

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
            line += f"\n{_LEVEL_COLORS.get('ERROR', '')}{exception.rstrip('\n')}{_RESET}"

        return line


# ── 自定义处理器 ──────────────────────────────────────────


def _capture_logger_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """从 _record 提取日志器名称，供 BracketConsoleRenderer 使用。

    必须在 ProcessorFormatter 的处理器链中运行（在 remove_processors_meta 之前），
    因为 _record 只在包装后的 LogRecord 中可用。
    """
    record = event_dict.get("_record")
    if record is not None:
        event_dict["_logger_name"] = record.name
    return event_dict


def _auto_exc_info(
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


def _add_trace_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """注入 trace_id / span_id / request_id。"""
    from app.core.trace import get_trace_context

    event_dict.update(get_trace_context())
    return event_dict


def _add_service_name(
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


# ── setup_structlog ──────────────────────────────────────


def setup_structlog() -> None:
    """配置 structlog 为全局日志处理器，启动时调用一次。

    - Console 输出 -> BracketConsoleRenderer（方括号格式）
    - File 输出    -> JSONRenderer（JSON 行，机器可解析）
    """
    from app.core.settings import get_settings

    settings = get_settings()
    obs = settings.observability
    log_level = getattr(logging, obs.logging.log_level.upper(), logging.INFO)

    # -- 公共处理器链（全局 + formatter 均使用，保证 stdlib logger 也有 trace context） --
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,               # event_dict["level"] = "info"/"error"/...
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_trace_context,                           # trace_id / span_id / request_id
        _add_service_name,                            # service 名称
        structlog.processors.TimeStamper(fmt="iso", utc=True),  # timestamp RFC 3339
        _auto_exc_info,                               # 自动捕获异常上下文
        structlog.processors.format_exc_info,          # 格式化为 "exception" 字符串字段
    ]

    # -- 配置 structlog 包（全局级） --
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # -- Console 输出格式化器（方括号格式） --
    console_renderer = BracketConsoleRenderer()
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _capture_logger_name,                         # 提取日志器名称（remove 前）
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )

    # -- File 输出格式化器（JSON） --
    json_renderer = structlog.processors.JSONRenderer()
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _capture_logger_name,                         # JSON 中也保留 logger_name
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            json_renderer,
        ],
    )

    log_file = Path(obs.logging.log_file)
    if not log_file.is_absolute():
        log_file = Path.cwd() / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # -- 配置 root logger --
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    root_logger.setLevel(log_level)

    # -- 第三方库降噪 --
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("python_multipart").setLevel(logging.WARNING)

    # asyncpg 保留 log_level（DEBUG 时打印 SQL 语句）
    logging.getLogger("asyncpg").setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志器。

    用法:
        logger = get_logger(__name__)
        logger.info("msg", event_type="retrieval", metadata={"doc_id": "123"})
        logger.error("msg", event_type="error", error="something went wrong")
    """
    return structlog.get_logger(name or __name__)


__all__ = [
    "setup_structlog",
    "get_logger",
]
