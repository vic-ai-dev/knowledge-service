"""通用日志模块 — structlog 结构化日志。

统一日志输出格式：

  [timestamp] [level] [logger] [trace_id] [span_id] [request_id] event  key=value  ...

同时输出 JSON 行到日志文件（供日志系统采集）。

属于 common 基础设施层，非 observability 范畴。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from app.common.log.structlog_processors import (
    add_service_name,
    add_trace_context,
    auto_exc_info,
    set_logger_name,
)
from structlog.dev import (
    Column,
    ConsoleRenderer,
    KeyValueColumnFormatter,
    LogLevelColumnFormatter,
)


# ── console timestamp formatter ─────────────────────────

def _format_timestamp_to_local(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """将 ISO UTC 时间戳转为本地时间（逗号毫秒），仅用于 Console 输出。

    原始: 2026-06-16T09:01:34.122363Z
    输出: 2026-06-16 18:01:00,163
    """
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


# ── setup_structlog ──────────────────────────────────────


def _build_columns(*, tracing_enabled: bool = True) -> list[Column]:
    """构建 ConsoleRenderer 的自定义列。

    参考格式:  timestamp LEVEL logger [trace_id] [span_id] [request_id] event key=value
    例如:      2026-06-16 18:01:00,163 INFO app.ingestion.pipeline ✓ File loaded  chunks=4

    当 tracing_enabled=False 时，省略 trace_id / span_id / request_id 列。
    """
    styles = ConsoleRenderer.get_default_column_styles(colors=True)
    level_styles = ConsoleRenderer.get_default_level_styles(colors=True)

    def _col(
        key: str,
        value_style: str,
        prefix: str = "",
        postfix: str = "",
    ) -> Column:
        return Column(
            key,
            KeyValueColumnFormatter(
                key_style=None,
                value_style=value_style,
                reset_style=styles.reset,
                value_repr=str,
                prefix=prefix,
                postfix=postfix,
            ),
        )

    columns: list[Column] = [
        # "2026-06-16 18:01:00,163 "
        _col("timestamp", styles.timestamp, prefix="", postfix=" "),
        # "INFO "  (5-char pad, no brackets)
        # Render level as styled uppercase string with trailing space
        Column(
            "level",
            KeyValueColumnFormatter(
                key_style=None,
                value_style=styles.bright,  # Will be overridden per level by processor
                reset_style=styles.reset,
                value_repr=str.upper,
                prefix="",
                postfix=" ",
            ),
        ),
        # "app.ingestion.pipeline "
        _col("logger_name", styles.bright + styles.logger_name, prefix="", postfix=" "),
    ]

    if tracing_enabled:
        columns.extend([
            _col("trace_id", styles.bright, prefix="[", postfix="] "),
            _col("span_id", styles.bright, prefix="[", postfix="] "),
            _col("request_id", styles.bright, prefix="[", postfix="] "),
        ])

    # Event/message — the primary log content (natural language)
    columns.append(_col("event", styles.bright, prefix="", postfix=""))

    # Default column: handles all remaining key=value pairs
    columns.append(
        Column(
            "",
            KeyValueColumnFormatter(
                key_style=styles.kv_key,
                value_style=styles.bright,
                reset_style=styles.reset,
                value_repr=str,
                width=0,
                prefix=" ",
            ),
        ),
    )

    return columns


def setup_structlog() -> None:
    """配置 structlog 为全局日志处理器，启动时调用一次。

    - Console 输出 -> ConsoleRenderer（彩色列格式）
    - File 输出    -> JSONRenderer（JSON 行，机器可解析）

    注意：必须在任何业务 import 之前调用，通常在 ``create_app()`` 第一行。
    """
    from app.core.settings import get_settings

    settings = get_settings()
    obs = settings.observability
    tracing_enabled = obs.tracing.enabled
    log_level = getattr(logging, obs.logging.log_level.upper(), logging.INFO)

    # -- 公共处理器链（全局 + formatter 均使用，保证 stdlib logger 也有 trace context） --
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_service_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        auto_exc_info,
        structlog.processors.format_exc_info,
    ]

    # 仅当 tracing 开启时才注入 trace context（本地开发减噪）
    if tracing_enabled:
        shared_processors.insert(2, add_trace_context)

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

    # -- Console 输出格式化器（列格式） --
    def _style_level_for_console(logger, method_name, event_dict):
        """Style the level field with ansi codes for console display."""
        from structlog.dev import ConsoleRenderer
        level = event_dict.get("level", "")
        if level:
            _styles = ConsoleRenderer.get_default_level_styles(colors=True)
            _reset = ConsoleRenderer.get_default_column_styles(colors=True).reset
            style = _styles.get(level.lower(), "")
            event_dict["level"] = f"{style}{level.upper()}{_reset}"
        return event_dict

    def _clean_service_for_console(logger, method_name, event_dict):
        """Remove 'service' key from console output (appended as key=value at end)."""
        event_dict.pop("service", None)
        return event_dict

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            set_logger_name,
            _format_timestamp_to_local,
            _style_level_for_console,
            _clean_service_for_console,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            ConsoleRenderer(columns=_build_columns(tracing_enabled=tracing_enabled)),
        ],
    )

    # -- File 输出格式化器（JSON） --
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

    # -- 配置 root logger（替代标准库的 basicConfig） --
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
    for logger_name in (
        "httpx",
        "urllib3",
        "httpcore",
        "hpack",
        "asyncio",
        "multipart",
        "python_multipart",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # asyncpg 保留 log_level（DEBUG 时打印 SQL 语句）
    logging.getLogger("asyncpg").setLevel(log_level)

    # -- 关闭 uvicorn 默认 access log（统一走 structlog middleware） --
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(log_level)

    # -- 确保所有 uvicorn 子日志器不绕开 structlog --
    for name in ("uvicorn", "uvicorn.asgi", "uvicorn.lifespan"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志器。

    用法:
        logger = get_logger(__name__)
        logger.info("msg", metadata={...})
        logger.error("msg", error="...")
    """
    return structlog.get_logger(name or __name__)


__all__ = [
    "setup_structlog",
    "get_logger",
]
