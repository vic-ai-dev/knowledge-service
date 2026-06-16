"""DocumentRepository — 文档注册表 CRUD。"""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model_cls = Document

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def find_by_id(self, doc_id: str | uuid.UUID) -> Document | None:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        return await super().find_by_id(doc_id)

    async def find_by_hash(self, file_hash: str) -> Document | None:
        stmt = select(Document).where(
            and_(Document.file_hash == file_hash, Document.is_deleted == False)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all_active(
        self,
        category: str | None = None,
        language: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        filters = [Document.is_deleted == False]
        if category:
            filters.append(Document.category == category)
        if language:
            filters.append(Document.language == language)

        total = await self.count(*filters)
        offset = (page - 1) * page_size
        rows = await self.find_all(
            *filters,
            order_by=Document.ingested_at.desc(),
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def soft_delete(self, doc_id: str | uuid.UUID) -> bool:
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)
        stmt = (
            update(Document)
            .where(and_(Document.id == doc_id, Document.is_deleted == False))
            .values(is_deleted=True, updated_at=func.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def batch_soft_delete(self, doc_ids: list[str | uuid.UUID]) -> int:
        ids = [uuid.UUID(d) if isinstance(d, str) else d for d in doc_ids]
        stmt = (
            update(Document)
            .where(and_(Document.id.in_(ids), Document.is_deleted == False))
            .values(is_deleted=True, updated_at=func.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def get_stats(self) -> dict:
        row = await self._session.execute(
            select(
                func.count().label("total_documents"),
                func.coalesce(func.sum(Document.file_size), 0).label("total_size_bytes"),
            ).where(Document.is_deleted == False)
        )
        stats_row = row.one()

        # by_category
        cat_rows = await self._session.execute(
            select(Document.category, func.count().label("cnt"))
            .where(Document.is_deleted == False)
            .group_by(Document.category)
        )
        by_category = {r.category: r.cnt for r in cat_rows}

        # by_language
        lang_rows = await self._session.execute(
            select(Document.language, func.count().label("cnt"))
            .where(Document.is_deleted == False)
            .group_by(Document.language)
        )
        by_language = {r.language: r.cnt for r in lang_rows}

        # by_type
        type_rows = await self._session.execute(
            select(Document.doc_type, func.count().label("cnt"))
            .where(Document.is_deleted == False)
            .group_by(Document.doc_type)
        )
        by_type = {r.doc_type: r.cnt for r in type_rows}

        return {
            "total_documents": stats_row.total_documents,
            "total_size_bytes": stats_row.total_size_bytes,
            "by_category": by_category,
            "by_language": by_language,
            "by_type": by_type,
        }


__all__ = ["DocumentRepository"]
