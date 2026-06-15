"""E13 — AI 知识助手 API（问答查询 + 对话历史 CRUD + 对话管理）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import (
    ConversationResponse,
    ConversationListResponse,
    MessageCreate,
)
from app.models.conversation import Conversation
from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask")
async def ask(
    query: str,
    search_mode: str = Query("hybrid"),
    collection: str | None = None,
    session_id: str | None = None,
):
    """AI 知识助手问答。

    使用 LLM 对检索结果进行总结回答。
    """
    # TODO(E13): 连接 LLM + QueryPipeline
    logger.info(
        "api_ask",
        message="AI 助手问答请求",
        metadata={"query": query, "search_mode": search_mode, "session_id": session_id},
    )
    return {
        "answer": "",
        "citations": [],
        "session_id": session_id or "",
        "trace_id": "",
        "latency_ms": 0.0,
    }


@router.get("/sessions")
async def list_sessions(
    kb_session: AsyncSession = Depends(get_kb_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出对话历史会话。"""
    repo = ConversationRepository(kb_session)
    rows, total = await repo.paginate(page=page, page_size=page_size)
    items = []
    for c in rows:
        items.append({
            "id": str(c.id),
            "title": c.title,
            "model": c.model,
            "message_count": c.message_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """获取指定会话的对话历史。"""
    repo = ConversationRepository(kb_session)
    conv = await repo.find_by_id(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": str(conv.id),
        "title": conv.title,
        "model": conv.model,
        "collection": conv.collection,
        "category": conv.category,
        "language": conv.language,
        "message_count": conv.message_count,
        "messages": conv.messages if conv.messages else [],
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """删除指定会话。"""
    repo = ConversationRepository(kb_session)
    deleted = await repo.soft_delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    await kb_session.commit()
    logger.info(
        "session_deleted",
        message="会话已删除",
        metadata={"session_id": session_id},
    )
    return {"status": "deleted", "session_id": session_id}


__all__ = ["router"]
