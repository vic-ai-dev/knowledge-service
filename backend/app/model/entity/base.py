"""SQLAlchemy 声明式基类。

使用两个独立的 declarative base：
- KnowledgeBase → knowledge 数据库
- RagBase       → knowledge_rag 数据库
"""

from sqlalchemy.orm import DeclarativeBase


class KnowledgeBase(DeclarativeBase):
    """knowledge 数据库的声明式基类。"""
    pass


class RagBase(DeclarativeBase):
    """knowledge_rag 数据库的声明式基类。"""
    pass


__all__ = ["KnowledgeBase", "RagBase"]
