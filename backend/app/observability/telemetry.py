"""OpenTelemetry 配置与辅助工具。

提供全局 tracer 和 trace_id 提取，替代手写的 app.core.trace 模块。
"""
from __future__ import annotations

import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from fastapi import FastAPI


_tracer: trace.Tracer | None = None


def setup_telemetry(app: FastAPI | None = None) -> None:
    """初始化 OpenTelemetry SDK 并可选注册 FastAPI 自动打点。

    分两步:
      1. 创建 TracerProvider + ConsoleSpanExporter（开发阶段输出 span 到 stdout）
      2. 如果传入 app 则调用 FastAPIInstrumentor
    """
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    global _tracer
    _tracer = trace.get_tracer("knowledge_service")

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    # 抑制第三方库的 span（减少噪音）
    from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
    BaseInstrumentor().instrument()


def get_tracer() -> trace.Tracer:
    """获取全局 tracer（应在 setup_telemetry 之后调用）。"""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("knowledge_service")
    return _tracer


def current_trace_uuid() -> uuid.UUID | None:
    """从当前 OpenTelemetry span 提取 trace_id 并转为 UUID。

    用于写入 ingestion_traces / query_traces 等数据库记录。
    如果没有活跃 span 则返回 None。
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return None
    return uuid.UUID(int=span_context.trace_id)


__all__ = [
    "setup_telemetry",
    "get_tracer",
    "current_trace_uuid",
]
