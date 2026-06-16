"""Conversation Pydantic Schemas。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from app.common.enums import SearchMode


class ConversationResponse(BaseModel):
    """对话记录返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    model: str = "default"
    category: str | None = None
    language: str | None = None
    message_count: int = 0
    messages: list = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class ConversationListResponse(BaseModel):
    """对话列表返回体。"""
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int


class MessageCreate(BaseModel):
    """消息创建请求。"""
    query: str
    search_mode: str = SearchMode.HYBRID.value
    session_id: str | None = None


__all__ = [
    "ConversationResponse",
    "ConversationListResponse",
    "MessageCreate",
]
