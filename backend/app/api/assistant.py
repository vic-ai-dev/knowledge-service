"""E13 — AI 知识助手 API（问答查询 + 对话历史 CRUD + 对话管理）。

此端点使用检索管线 + LLM 生成回答。
"""

from __future__ import annotations

import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import (
    ConversationResponse,
    ConversationListResponse,
    MessageCreate,
)
from app.schemas.assistant import AskRequest
from app.models.conversation import Conversation
from app.common.log import get_logger

from app.core.query_engine.query_processor import QueryProcessor
from app.core.query_engine.hybrid_search import HybridSearch
from app.libs.factory import LLMFactory

logger = get_logger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask")
async def ask(body: AskRequest):
    """AI 知识助手问答。

    执行检索 → 用 LLM 对检索结果进行总结回答。
    """
    t0 = time.monotonic()
    logger.info(
        "api_ask",
        message="AI 助手问答请求",
        metadata={"query": body.query, "search_mode": body.search_mode, "rerank": body.rerank},
    )

    try:
        # 1. 构建检索查询
        processor = QueryProcessor()
        rq = processor.process(
            query_text=body.query,
            search_mode=body.search_mode,
            top_k=10,
            rerank=body.rerank,
        )

        # 2. 执行检索
        searcher = HybridSearch()
        search_result = await searcher.search(rq)

        # 3. 准备上下文
        context_parts = []
        citations = []
        for r in search_result.results[:5]:
            context_parts.append(
                f"[来源: {r.source_path or 'unknown'}]\n{r.text}"
            )
            citations.append({
                "chunk_id": r.chunk_id,
                "text": r.text[:200],
                "source": r.source_path or "unknown",
            })

        context = "\n\n---\n\n".join(context_parts)

        # 4. 调用 LLM 生成回答
        system_prompt = (
            "你是一个企业知识助手。请根据提供的检索结果回答用户问题。"
            "如果检索结果不足以回答问题，请如实告知。"
            "请引用来源（使用 [来源: filename] 格式）。\n\n"
            "检索结果：\n"
            f"{context}"
        )

        llm = LLMFactory.create()
        llm_response = await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.query},
            ],
        )

        total_latency_ms = round((time.monotonic() - t0) * 1000, 2)

        logger.info(
            "api_ask_done",
            message="AI 助手回答完成",
            metadata={
                "query": body.query,
                "latency_ms": total_latency_ms,
                "citations": len(citations),
                "llm_model": llm_response.model,
            },
        )

        return {
            "query": body.query,
            "results": [r.__dict__ for r in search_result.results],
            "trace_id": search_result.trace_id,
            "total_latency_ms": total_latency_ms,
            "answer": llm_response.content,
            "citations": citations,
        }

    except Exception as e:
        total_latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.error(
            "api_ask_error",
            error=str(e),
            metadata={"query": body.query, "latency_ms": total_latency_ms},
        )
        raise HTTPException(status_code=500, detail=f"问答生成失败: {str(e)}")


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
    try:
        parsed = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 session_id 格式")
    repo = ConversationRepository(kb_session)
    conv = await repo.find_by_id(parsed)
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
    try:
        parsed = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 session_id 格式")
    repo = ConversationRepository(kb_session)
    deleted = await repo.soft_delete(parsed)
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
