"""OpenTelemetry 配置与辅助工具。

提供全局 tracer 和 trace_id 提取，替代手写的 app.common.trace 模块。
"""
from __future__ import annotations

import uuid

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from fastapi import FastAPI


_tracer: trace.Tracer | None = None


def setup_telemetry(app: FastAPI | None = None) -> None:
    """初始化 OpenTelemetry SDK 并可选注册 FastAPI 自动打点。"""
    provider = TracerProvider()
    # FIXME 开发阶段屏蔽 ConsoleExporter 避免干扰 stdout。
    #       生产环境应替换为 OTLPSpanExporter（Jaeger / Tempo / Zipkin）：
    #
    #       from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    #       provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="...")))
    trace.set_tracer_provider(provider)

    global _tracer
    _tracer = trace.get_tracer("knowledge_service")

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> trace.Tracer:
    """获取全局 tracer（应在 setup_telemetry 之后调用）。"""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("knowledge_service")
    return _tracer


def current_trace_uuid() -> uuid.UUID | None:
    """从当前 OpenTelemetry span 提取 trace_id 并转为 UUID。"""
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
