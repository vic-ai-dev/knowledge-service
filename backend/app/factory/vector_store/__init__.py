"""VectorStore 实现包 — 导入即触发工厂注册。"""

from app.factory.vector_store.pgvector_impl import PGVectorStore
from app.factory.factory import VectorStoreFactory

# ── 注册默认实现 ────────────────────────────────────────────

VectorStoreFactory.register("pgvector", PGVectorStore)

__all__ = ["PGVectorStore"]
