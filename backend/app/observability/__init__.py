"""可观测性基础设施 — structlog 结构化日志。

配置 structlog 输出 JSON 格式日志，固定字段：
  - timestamp (ISO 8601 UTC)
  - level (DEBUG / INFO / WARNING / ERROR / CRITICAL)
  - service (服务标识, 如 knowledge_service)
  - trace_id / span_id / parent_span_id (分布式追踪)
  - request_id (前端请求 ID)
  - event_type (http_request / http_response / llm_call / retrieval / error 等)
  - message (人类可读日志消息)
  - metadata (业务上下文: 会话 ID、文档 ID、耗时等)
  - error (仅 ERROR 级别)
  - stack_trace (仅 ERROR 级别)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog


def _add_trace_context(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict,
) -> dict:
    """向日志事件注入 TraceContext 字段。"""
    from app.core.trace import get_trace_context

    event_dict.update(get_trace_context())
    return event_dict


def _add_service_name(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict,
) -> dict:
    """注入服务名称。"""
    from app.core.settings import get_settings

    try:
        event_dict["service"] = get_settings().observability.logging.service_name
    except Exception:
        event_dict["service"] = "knowledge_service"
    return event_dict


def setup_structlog() -> None:
    """配置 structlog 为全局日志处理器。

    应在应用启动时调用一次。
    """
    from app.core.settings import get_settings

    settings = get_settings()
    obs = settings.observability
    log_level = getattr(logging, obs.logging.log_level.upper(), logging.INFO)

    # ── structlog processors ──
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_trace_context,
        _add_service_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    # 配置 structlog 包
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

    # ── 输出格式化器（用于标准 logging handler） ──
    json_renderer = structlog.processors.JSONRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            json_renderer,
        ],
    )

    # ── stdout handler ──
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # ── file handler ──
    log_file = Path(obs.logging.log_file)
    if not log_file.is_absolute():
        log_file = Path.cwd() / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    # ── 配置 root logger ──
    root_logger = logging.getLogger()
    # 清除已有 handler 避免重复
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level)

    # ── 第三方库降噪 ──
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


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
