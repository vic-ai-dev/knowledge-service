"""日志模块 — structlog 配置与处理器。

提供全局结构化日志配置（setup_structlog）和便捷日志器获取（get_logger）。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.dev import Column, ConsoleRenderer, KeyValueColumnFormatter


# ── structlog 自定义处理器 ────────────────────────────────


def set_logger_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """从 _record 提取日志器全名，供 ConsoleRenderer 列使用。"""
    record = event_dict.get("_record")
    if record is not None:
        event_dict["logger_name"] = record.name
    return event_dict


def auto_exc_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """自动捕获异常上下文中的 exc_info。"""
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
    """从 OpenTelemetry 注入 trace_id / span_id / request_id。"""
    from opentelemetry import trace as ot_trace
    span = ot_trace.get_current_span()
    sc = span.get_span_context()
    if sc.is_valid:
        event_dict["trace_id"] = format(sc.trace_id, "032x")
        event_dict["span_id"] = format(sc.span_id, "016x")
    return event_dict


def add_service_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """注入 service 标识。"""
    from app.common.settings import get_settings
    try:
        event_dict["service"] = get_settings().observability.logging.service_name
    except Exception:
        event_dict["service"] = "knowledge_service"
    return event_dict


# ── Console 时间戳格式化 ──────────────────────────────────


def _format_timestamp_to_local(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """将 ISO UTC 时间戳转为本地时间（逗号毫秒），仅用于 Console 输出。"""
    ts = event_dict.get("timestamp")
    if ts and isinstance(ts, str):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            ms = dt.microsecond // 1000
            event_dict["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S") + f",{ms:03d}"
        except Exception:
            pass
    return event_dict


# ── ConsoleRenderer 列构建 ────────────────────────────────


def _build_columns(*, tracing_enabled: bool = True) -> list[Column]:
    """构建 ConsoleRenderer 的自定义列。"""
    styles = ConsoleRenderer.get_default_column_styles(colors=True)

    def _col(key: str, value_style: str, prefix: str = "", postfix: str = "") -> Column:
        return Column(
            key,
            KeyValueColumnFormatter(
                key_style=None, value_style=value_style,
                reset_style=styles.reset, value_repr=str,
                prefix=prefix, postfix=postfix,
            ),
        )

    columns: list[Column] = [
        _col("timestamp", styles.timestamp, prefix="", postfix=" "),
        _col("level", styles.bright, prefix="", postfix=" "),
        _col("logger_name", styles.bright + styles.logger_name, prefix="", postfix=" "),
    ]
    if tracing_enabled:
        columns.extend([
            _col("trace_id", styles.bright, prefix="[", postfix="] "),
            _col("span_id", styles.bright, prefix="[", postfix="] "),
            _col("request_id", styles.bright, prefix="[", postfix="] "),
        ])
    columns.append(_col("event", styles.bright, prefix="", postfix=""))
    columns.append(Column("", KeyValueColumnFormatter(
        key_style=styles.kv_key, value_style=styles.bright,
        reset_style=styles.reset, value_repr=str, width=0, prefix=" ",
    )))
    return columns


# ── structlog 全局配置 ────────────────────────────────────


def setup_structlog() -> None:
    """配置 structlog 为全局日志处理器，启动时调用一次。"""
    from app.common.settings import get_settings
    settings = get_settings()
    obs = settings.observability
    tracing_enabled = obs.tracing.enabled
    log_level = getattr(logging, obs.logging.log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_service_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        auto_exc_info,
        structlog.processors.format_exc_info,
    ]
    if tracing_enabled:
        shared_processors.insert(2, add_trace_context)

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

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            set_logger_name,
            _format_timestamp_to_local,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            ConsoleRenderer(columns=_build_columns(tracing_enabled=tracing_enabled)),
        ],
    )
    json_renderer = structlog.processors.JSONRenderer()
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            set_logger_name,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            json_renderer,
        ],
    )

    log_file = Path(obs.logging.log_file)
    if not log_file.is_absolute():
        log_file = Path.cwd() / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level)

    for n in ("pdfminer", "httpx", "urllib3", "httpcore", "hpack", "asyncio", "multipart", "python_multipart"):
        logging.getLogger(n).setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(log_level)
    for n in ("uvicorn", "uvicorn.asgi", "uvicorn.lifespan"):
        lg = logging.getLogger(n)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志器。"""
    return structlog.get_logger(name or __name__)


__all__ = [
    "set_logger_name",
    "auto_exc_info",
    "add_trace_context",
    "add_service_name",
    "setup_structlog",
    "get_logger",
]
