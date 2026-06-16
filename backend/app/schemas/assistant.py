"""Assistant Pydantic Schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field
from app.common.enums import SearchMode


class AskRequest(BaseModel):
    """AI 知识助手问答请求体。"""
    query: str
    search_mode: str = SearchMode.HYBRID.value
    rerank: bool = True
    session_id: str | None = None


__all__ = [
    "AskRequest",
]
