"""DocumentChunkRepository — Chunk 数据 CRUD（knowledge_rag 库）。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.entity.chunk import DocumentChunk
from app.repositories.base import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model_cls = DocumentChunk

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_by_document(
        self,
        doc_id: str | uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DocumentChunk], int]:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        filters = [DocumentChunk.doc_id == doc_id]
        total = await self.count(*filters)
        offset = (page - 1) * page_size
        rows = await self.find_all(
            *filters,
            order_by=DocumentChunk.chunk_index,
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def delete_by_document(self, doc_id: str | uuid.UUID) -> int:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        stmt = sa_delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def batch_delete_by_document(self, doc_ids: list[str | uuid.UUID]) -> int:
        ids = [uuid.UUID(d) if isinstance(d, str) else d for d in doc_ids]
        stmt = sa_delete(DocumentChunk).where(DocumentChunk.doc_id.in_(ids))
        result = await self._session.execute(stmt)
        return result.rowcount

    async def count_by_document(self, doc_id: str | uuid.UUID) -> int:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        return await self.count(DocumentChunk.doc_id == doc_id)

    async def get_total_count(self) -> int:
        return await self.count()


__all__ = ["DocumentChunkRepository"]
