"""Ingestion Repositories — 摄入历史与追踪 CRUD。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import IngestionHistory, IngestionTrace
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

    async def paginate(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[IngestionHistory], int]:
        total = await self.count()
        offset = (page - 1) * page_size
        rows = await self.find_all(
            order_by=IngestionHistory.created_at.desc(),
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def update_status(
        self,
        record_id: str | uuid.UUID,
        status: str,
        error_message: str | None = None,
        **kwargs,
    ) -> bool:
        if isinstance(record_id, str):
            record_id = uuid.UUID(record_id)
        values = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        values.update(kwargs)
        stmt = (
            update(IngestionHistory)
            .where(IngestionHistory.id == record_id)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class IngestionTraceRepository(BaseRepository[IngestionTrace]):
    model_cls = IngestionTrace

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def paginate(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[IngestionTrace], int]:
        total = await self.count()
        offset = (page - 1) * page_size
        rows = await self.find_all(
            order_by=IngestionTrace.created_at.desc(),
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def find_by_trace_id(
        self, trace_id: str | uuid.UUID
    ) -> IngestionTrace | None:
        if isinstance(trace_id, str):
            trace_id = uuid.UUID(trace_id)
        return await super().find_by_id(trace_id)

    # Override: IngestionTrace uses trace_id as PK, not 'id'
    async def find_by_id(self, id_val: str | uuid.UUID) -> IngestionTrace | None:
        if isinstance(id_val, str):
            id_val = uuid.UUID(id_val)
        stmt = select(IngestionTrace).where(IngestionTrace.trace_id == id_val)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["IngestionHistoryRepository", "IngestionTraceRepository"]
