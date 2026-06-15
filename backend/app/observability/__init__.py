"""可观测性基础设施 — structlog 结构化日志（入口）。

将渲染器和处理器拆分到 :mod:`renderers` 和 :mod:`processors` 子模块，
本模块仅暴露 ``setup_structlog()`` 和 ``get_logger()`` 作为公共 API。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from app.observability.structlog_processors import (
    add_service_name,
    add_trace_context,
    auto_exc_info,
    capture_logger_name,
)
from app.observability.renderers import BracketConsoleRenderer


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
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_trace_context,
        add_service_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        auto_exc_info,
        structlog.processors.format_exc_info,
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
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            capture_logger_name,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            BracketConsoleRenderer(),
        ],
    )

    # -- File 输出格式化器（JSON） --
    json_renderer = structlog.processors.JSONRenderer()
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            capture_logger_name,
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
    for logger_name in ("httpx", "urllib3", "httpcore", "hpack", "asyncio", "multipart", "python_multipart"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

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
