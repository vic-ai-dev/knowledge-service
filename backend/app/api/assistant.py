"""E13 — AI 知识助手 API（问答查询 + 对话历史 CRUD + 对话管理）。

此端点使用检索管线 + LLM 生成回答，并自动保存对话记录与查询追踪。
"""

from __future__ import annotations

import uuid
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_sa import get_kb_session
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.query_repo import QueryTraceRepository
from app.schemas.conversation import (
    ConversationResponse,
    ConversationListResponse,
    MessageCreate,
)
from app.schemas.assistant import AskRequest
from app.models.conversation import Conversation
from app.models.query import QueryTrace
from app.common.log import get_logger

from app.core.query_engine.query_processor import QueryProcessor
from app.core.query_engine.hybrid_search import HybridSearch
from app.libs.factory import LLMFactory

logger = get_logger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask")
async def ask(
    body: AskRequest,
    kb_session: AsyncSession = Depends(get_kb_session),
):
    """AI 知识助手问答。

    执行检索 → 用 LLM 对检索结果进行总结回答 → 保存对话记录与查询追踪。
    """
    t0 = time.monotonic()
    logger.info(
        "api_ask",
        message="AI 助手问答请求",
        metadata={
            "query": body.query,
            "search_mode": body.search_mode,
            "rerank": body.rerank,
            "session_id": body.session_id,
        },
    )

    conv_repo = ConversationRepository(kb_session)
    query_repo = QueryTraceRepository(kb_session)

    # ── 1. 对话管理：创建或复用会话 ──
    if body.session_id:
        try:
            conv_id = uuid.UUID(body.session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 session_id")
        conv = await conv_repo.find_by_id(conv_id)
        if conv is None:
            # session_id 对应的会话已被删除或不存在，创建新会话
            conv = Conversation(
                title=body.query[:60] or "新对话",
                messages=[],
                message_count=0,
            )
            await conv_repo.save(conv)
    else:
        conv = Conversation(
            title=body.query[:60] or "新对话",
            messages=[],
            message_count=0,
        )
        await conv_repo.save(conv)

    try:
        # ── 2. 检索阶段 ──
        processor = QueryProcessor()
        rq = processor.process(
            query_text=body.query,
            search_mode=body.search_mode,
            top_k=10,
            rerank=body.rerank,
        )

        searcher = HybridSearch()
        search_result = await searcher.search(rq)
        t1 = time.monotonic()
        search_latency_ms = round((t1 - t0) * 1000, 2)

        # ── 3. 准备上下文 ──
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

        # ── 4. LLM 生成 ──
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
        t2 = time.monotonic()
        llm_latency_ms = round((t2 - t1) * 1000, 2)
        total_latency_ms = round((t2 - t0) * 1000, 2)

        # ── 5. 保存对话记录 ──
        now_str = datetime.utcnow().isoformat()
        user_msg: dict = {"role": "user", "content": body.query, "timestamp": now_str}
        assistant_msg: dict = {
            "role": "assistant",
            "content": llm_response.content,
            "timestamp": now_str,
            "citations": citations,
        }

        # 重新赋值 messages 以触发 SQLAlchemy JSONB 变更追踪
        existing_msgs: list[dict] = list(conv.messages) if conv.messages else []
        existing_msgs.append(user_msg)
        existing_msgs.append(assistant_msg)
        conv.messages = existing_msgs
        conv.message_count += 2
        # 更新标题为第一条用户消息的前缀
        if conv.message_count <= 2:
            conv.title = body.query[:60] or "新对话"

        await conv_repo.update(conv)

        # ── 6. 保存 QueryTrace ──
        usage = llm_response.usage or {}
        trace_id_str = search_result.trace_id or str(uuid.uuid4())
        try:
            trace_id_uuid = uuid.UUID(trace_id_str)
        except ValueError:
            trace_id_uuid = uuid.uuid4()

        top_k_short = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text[:200],
                "score": r.score,
                "source": r.source_path,
            }
            for r in search_result.results[:5]
        ]

        query_trace = QueryTrace(
            trace_id=trace_id_uuid,
            user_query=body.query,
            total_latency_ms=int(total_latency_ms),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cache_hit=False,
            rejected=False,
            stages={
                "search_latency_ms": search_latency_ms,
                "llm_latency_ms": llm_latency_ms,
            },
            top_k_results=top_k_short,
        )
        await query_repo.save(query_trace)

        await kb_session.commit()

        logger.info(
            "api_ask_done",
            message="AI 助手回答完成",
            metadata={
                "query": body.query,
                "session_id": str(conv.id),
                "latency_ms": total_latency_ms,
                "citations": len(citations),
                "llm_model": llm_response.model,
            },
        )

        return {
            "session_id": str(conv.id),
            "query": body.query,
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "score": r.score,
                    "source_path": r.source_path,
                    "metadata": r.metadata,
                }
                for r in search_result.results
            ],
            "trace_id": trace_id_str,
            "total_latency_ms": total_latency_ms,
            "answer": llm_response.content,
            "citations": citations,
        }

    except Exception as e:
        total_latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.error(
            "api_ask_error",
            error=str(e),
            metadata={
                "query": body.query,
                "session_id": str(conv.id),
                "latency_ms": total_latency_ms,
            },
        )

        # 即使出错也保存用户消息和错误消息
        now_str = datetime.utcnow().isoformat()
        err_user_msg: dict = {"role": "user", "content": body.query, "timestamp": now_str}
        err_assistant_msg: dict = {
            "role": "assistant",
            "content": f"抱歉，回答生成失败了。错误信息: {str(e)}",
            "timestamp": now_str,
        }
        existing_msgs = list(conv.messages) if conv.messages else []
        existing_msgs.append(err_user_msg)
        existing_msgs.append(err_assistant_msg)
        conv.messages = existing_msgs
        conv.message_count += 2

        # 保存 QueryTrace（标记为 rejected）
        try:
            error_trace = QueryTrace(
                trace_id=uuid.uuid4(),
                user_query=body.query,
                    total_latency_ms=int(total_latency_ms),
                rejected=True,
                rejection_reason=str(e),
                error=str(e)[:500],
            )
            await query_repo.save(error_trace)
        except Exception:
            logger.error("save_query_trace_error", error="Failed to save error trace")

        await kb_session.commit()

        raise HTTPException(status_code=500, detail=f"问答生成失败: {str(e)}")


@router.get("/sessions", response_model=ConversationListResponse)
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
