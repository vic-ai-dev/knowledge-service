"""Pipeline 进度回调机制。

为 Ingestion Pipeline / Query Pipeline 提供统一的进度报告约定。
Pipeline 在各阶段调用 ProgressCallback 向外报告进度，
WebSocket / 测试代码通过该回调获取实时状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.common.enums import PipelineStage



@dataclass
class PipelineProgress:
    """Pipeline 进度数据。"""

    run_id: str
    stage: PipelineStage
    progress: float = 0.0  # 0.0 ~ 1.0
    message: str = ""
    total: int = 0
    current: int = 0
    metadata: dict = field(default_factory=dict)


# ── 回调类型 ─────────────────────────────────────────────

ProgressCallback = Callable[[PipelineProgress], None]


class NoOpProgressCallback:
    """空回调 — 不执行任何操作。"""

    def __call__(self, progress: PipelineProgress) -> None:
        pass


class LoggingProgressCallback:
    """日志回调 — 每次进度更新写日志。"""

    def __init__(self, logger_name: str | None = None):
        from app.common.log import get_logger

        self.logger = get_logger(logger_name or "pipeline.progress")

    def __call__(self, progress: PipelineProgress) -> None:
        self.logger.info(
            "pipeline_progress",
            metadata={
                "run_id": progress.run_id,
                "stage": progress.stage.value,
                "progress": progress.progress,
                "message": progress.message,
                "total": progress.total,
                "current": progress.current,
            },
        )


__all__ = [
    "PipelineStage",
    "PipelineProgress",
    "ProgressCallback",
    "NoOpProgressCallback",
    "LoggingProgressCallback",
]
