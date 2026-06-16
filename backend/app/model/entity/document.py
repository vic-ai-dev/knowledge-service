"""Document ORM 模型 — 文档注册表（knowledge 库）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.model.entity.base import KnowledgeBase


class Document(KnowledgeBase):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="知识分类: employee_handbook / compliance / technical_spec / architecture",
    )
    language: Mapped[str] = mapped_column(
        String, nullable=False, comment="语言: zh (中文) / en (英文)"
    )
    doc_type: Mapped[str] = mapped_column(
        String, nullable=False, comment="文件格式: pdf / md / html"
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["Document"]
