"""Image ORM 模型 — 图片索引（knowledge 库）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.model.entity.base import KnowledgeBase


class ImageIndex(KnowledgeBase):
    __tablename__ = "image_index"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    image_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    doc_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    page_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


__all__ = ["ImageIndex"]
