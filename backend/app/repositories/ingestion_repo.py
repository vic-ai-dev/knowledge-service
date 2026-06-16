"""Ingestion Repositories — 摄入历史与追踪 CRUD。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.entity.ingestion import IngestionHistory, IngestionTrace
from app.repositories.base import BaseRepository


class IngestionHistoryRepository(BaseRepository[IngestionHistory]):
    model_cls = IngestionHistory

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_by_hash(self, file_hash: str) -> IngestionHistory | None:
        stmt = (
            select(IngestionHistory)
            .where(IngestionHistory.file_hash == file_hash)
            .order_by(IngestionHistory.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_document_id(self, doc_id: str | uuid.UUID) -> IngestionTrace | None:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        stmt = (
            select(IngestionTrace)
            .where(IngestionTrace.document_id == doc_id)
            .order_by(IngestionTrace.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class IngestionTraceRepository(BaseRepository[IngestionTrace]):
    """Ingestion Trace 仓储 — trace_id 为主键。"""

    model_cls = IngestionTrace

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_by_trace_id(self, trace_id: str | uuid.UUID) -> IngestionTrace | None:
        """按 trace_id 查询。"""
        if isinstance(trace_id, str):
            trace_id = uuid.UUID(trace_id)
        stmt = select(IngestionTrace).where(IngestionTrace.trace_id == trace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_source_path(self, source_path: str) -> IngestionTrace | None:
        """按 source_path 查询最新一条。"""
        stmt = (
            select(IngestionTrace)
            .where(IngestionTrace.source_path == source_path)
            .order_by(IngestionTrace.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[IngestionTrace], int]:
        """分页查询。"""
        base_q = self._build_base_query().order_by(IngestionTrace.created_at.desc())
        total_q = select(func.count()).select_from(IngestionTrace)

        total_result = await self._session.execute(total_q)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = base_q.offset(offset).limit(page_size)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return rows, total


__all__ = ["IngestionHistoryRepository", "IngestionTraceRepository"]
