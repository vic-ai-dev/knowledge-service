"""ConversationRepository — 对话记录 CRUD。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model_cls = Conversation

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def paginate(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Conversation], int]:
        total = await self.count()
        offset = (page - 1) * page_size
        rows = await self.find_all(
            order_by=Conversation.created_at.desc(),
            limit=page_size,
            offset=offset,
        )
        return rows, total

    async def soft_delete(self, conv_id: str | uuid.UUID) -> bool:
        if isinstance(conv_id, str):
            conv_id = uuid.UUID(conv_id)
        instance = await self.find_by_id(conv_id)
        if instance is None:
            return False
        await self.delete(instance)
        return True


__all__ = ["ConversationRepository"]
