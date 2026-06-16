"""Evaluation Pydantic Schemas。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class EvaluationResultResponse(BaseModel):
    """评估结果返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    metrics: dict
    test_set: str | None = None
    backends_used: list[str] | None = None
    created_at: str | None = None


class EvaluationResultListResponse(BaseModel):
    """评估结果列表返回体。"""
    items: list[EvaluationResultResponse]
    total: int
    page: int
    page_size: int


class GoldenTestSetResponse(BaseModel):
    """黄金测试集返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    queries: list[dict]
    category: str | None = None
    language: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GoldenTestSetListResponse(BaseModel):
    """黄金测试集列表返回体。"""
    items: list[GoldenTestSetResponse]
    total: int
    page: int
    page_size: int


class EvalRunRequest(BaseModel):
    """评估运行请求。"""
    test_set_id: str | None = None
    search_mode: str = "hybrid"
    top_k: int = 10
    rerank: bool = True


class EvalRunResponse(BaseModel):
    """评估运行响应。"""
    task_id: str
    status: str
    completed: int = 0
    total: int = 0
    error: str | None = None


__all__ = [
    "EvaluationResultResponse",
    "EvaluationResultListResponse",
    "GoldenTestSetResponse",
    "GoldenTestSetListResponse",
    "EvalRunRequest",
    "EvalRunResponse",
]
