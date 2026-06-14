"""E13 — AI 知识助手 API（问答查询 + 对话历史 CRUD + 对话管理）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.observability import get_logger

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
        event_type="llm_call",
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出对话历史会话。"""
    # TODO(E13): 从数据库读取会话列表
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的对话历史。"""
    # TODO(E13): 从数据库读取对话详情
    return {"session_id": session_id, "messages": []}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话。"""
    # TODO(E13): 从数据库删除会话
    logger.info(
        "session_deleted",
        event_type="http_request",
        message="会话已删除",
        metadata={"session_id": session_id},
    )
    return {"status": "deleted", "session_id": session_id}


__all__ = ["router"]
