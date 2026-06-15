"""BaseRepository — 通用 CRUD 抽象基类 + SQLAlchemy 2.0 实现。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T]):
    """通用仓库基类，封装 SQLAlchemy 2.0 async CRUD 操作。"""

    model_cls: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── 查询 ────────────────────────────────────────────

    async def find_by_id(self, id_val: Any) -> T | None:
        stmt = select(self.model_cls).where(self.model_cls.id == id_val)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(
        self,
        *filters: Any,
        order_by: Any | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        stmt = select(self.model_cls)
        for f in filters:
            if f is not None:
                stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model_cls)
        for f in filters:
            if f is not None:
                stmt = stmt.where(f)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── 写入 ────────────────────────────────────────────

    async def save(self, instance: T) -> T:
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def save_all(self, instances: list[T]) -> list[T]:
        self._session.add_all(instances)
        await self._session.flush()
        return instances

    async def update(self, instance: T, **kwargs: Any) -> T:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def delete(self, instance: T) -> None:
        await self._session.delete(instance)
        await self._session.flush()

    def _build_base_query(self) -> Select:
        """构建基础查询，子类可覆盖以添加默认过滤。"""
        return select(self.model_cls)


__all__ = ["BaseRepository"]
