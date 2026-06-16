"""查询管线 — 检索 + LLM 生成 + 追踪记录。

用法:
    pipeline = QueryPipeline()
    result = await pipeline.execute("query", kb_session=session)
"""

from __future__ import annotations

import uuid
import time
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.query_engine import QueryProcessor, HybridSearch
from app.common.types import QueryResult, RetrievalResult
from app.common.log import get_logger
from app.common.enums import SearchMode
from app.model.entity.query import QueryTrace
from app.repositories.query_repo import QueryTraceRepository

logger = get_logger(__name__)

# ── 加载系统提示词模板 ──
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "query_system_prompt.txt"
_SYSTEM_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


class QueryPipeline:
    """查询管线：检索 → LLM 生成 → 追踪记录。"""

    def __init__(self) -> None:
        self._processor = QueryProcessor()
        self._searcher = HybridSearch()

    async def execute(
        self,
        query_text: str,
        search_mode: str = SearchMode.HYBRID.value,
        top_k: int = 10,
        rerank: bool = True,
        kb_session: AsyncSession | None = None,
    ) -> QueryResult:
        """执行查询管线（检索 + LLM 生成 + 可选的 QueryTrace 保存）。

        Args:
            query_text: 用户查询文本。
            search_mode: ``hybrid`` 或 ``vector_only``。
            top_k: 返回的最大结果数。
            rerank: 是否启用重排序。
            kb_session: knowledge 数据库会话（传入则自动保存 QueryTrace）。

        Returns:
            QueryResult，包含检索结果、LLM 回答和引用。
        """
        t_start = time.monotonic()

        # ── 1. 处理查询参数 ──
        rq = self._processor.process(
            query_text=query_text,
            search_mode=search_mode,
            top_k=top_k,
            rerank=rerank,
        )

        # ── 2. 检索阶段 ──
        search_result = await self._searcher.search(rq)

        # ── 3. 解析文档标题 ──
        # 查询 documents 表获取标题，替换 results 中的 source_path
        from app.repositories.document_repo import DocumentRepository
        doc_ids = list({r.doc_id for r in search_result.results if r.doc_id})
        title_map: dict[str, str] = {}
        if doc_ids and kb_session is not None:
            doc_repo = DocumentRepository(kb_session)
            for did in doc_ids:
                doc = await doc_repo.find_by_id(did)
                if doc and doc.title:
                    title_map[did] = doc.title

        # 替换 results 中的 source_path 为 document.title
        for i, r in enumerate(search_result.results):
            title = title_map.get(r.doc_id) if r.doc_id else None
            if title:
                search_result.results[i] = RetrievalResult(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    metadata=r.metadata,
                    score=r.score,
                    title=title,
                    doc_id=r.doc_id,
                )

        # ── 4. 准备上下文 (top-5) 按 source 分组 ──
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)
        for r in search_result.results[:5]:
            groups[r.title or "unknown"].append(r)

        context_parts: list[str] = []
        citations: list[dict[str, Any]] = []
        for src, items in groups.items():
            combined = "\n\n".join(item.text for item in items)
            context_parts.append(f"[来源: {src}]\n{combined}")
            first = items[0]
            citations.append({
                "chunk_id": first.chunk_id,
                "text": first.text[:200],
                "source": src,
            })
        context = "\n\n---\n\n".join(context_parts)

        # ── 4. LLM 生成 ──
        from app.factory.factory import LLMFactory

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.replace(
            "{context}", context
        ).replace("{question}", query_text)

        llm = LLMFactory.create()
        llm_response = await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query_text},
            ],
        )

        total_latency_ms = round((time.monotonic() - t_start) * 1000, 2)

        # ── 5. 检测否定回答 ──
        raw_answer = llm_response.content or ""
        rejected = raw_answer.lstrip().upper().startswith("UNABLE_TO_ANSWER")
        if rejected:
            # 去掉 "UNABLE_TO_ANSWER" 前缀，剩余内容作为最终回答
            cleaned = raw_answer[len("UNABLE_TO_ANSWER"):].strip().lstrip(":：,， ").strip()
            answer = cleaned or "抱歉，当前知识库中没有找到相关信息。"
        else:
            answer = raw_answer

        # ── 6. 组装结果 ──
        result = QueryResult(
            query=query_text,
            results=search_result.results,
            trace_id=search_result.trace_id or str(uuid.uuid4()),
            total_latency_ms=total_latency_ms,
            answer=answer,
            citations=citations,
            usage=llm_response.usage or {},
            llm_model=llm_response.model or "",
            rejected=rejected,
        )

        # ── 6. 保存 QueryTrace ──
        if kb_session is not None:
            await self._save_trace(kb_session, query_text, rq, result)

        logger.info(
            "pipeline_completed",
            metadata={
                "query": query_text[:80],
                "search_mode": search_mode,
                "results": len(result.results),
                "total_latency_ms": total_latency_ms,
            },
        )

        return result

    # ── 追踪写入 ──────────────────────────────────────

    async def _save_trace(
        self,
        session: AsyncSession,
        query_text: str,
        rq: Any,
        result: QueryResult,
    ) -> None:
        """将查询结果写入 query_traces 表。"""
        usage = result.usage or {}
        cache_hit = False  # 预留字段，供后续 Query Cache 使用

        try:
            trace_id_uuid = uuid.UUID(result.trace_id)
        except ValueError:
            trace_id_uuid = uuid.uuid4()

        top_k_short = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text[:200],
                "score": r.score,
                "source": r.title,
            }
            for r in result.results[:5]
        ]

        trace = QueryTrace(
            trace_id=trace_id_uuid,
            user_query=query_text,
            search_mode=getattr(rq, "search_mode", None),
            rerank=getattr(rq, "rerank", None),
            total_latency_ms=int(result.total_latency_ms),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
            cache_hit=cache_hit,
            rejected=result.rejected,
            stages={"total_latency_ms": result.total_latency_ms},
            top_k_results=top_k_short,
            results=result.answer,
        )

        repo = QueryTraceRepository(session)
        await repo.save(trace)
        await session.commit()

        logger.debug("query_trace_saved", metadata={"trace_id": str(trace_id_uuid)})


__all__ = ["QueryPipeline"]
