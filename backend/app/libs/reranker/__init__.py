"""Reranker 实现包 — 导入即触发工厂注册。"""

from app.libs.reranker.cross_encoder import CrossEncoderReranker
from app.libs.factory import RerankerFactory

# ── 注册默认实现 ────────────────────────────────────────────

RerankerFactory.register("cross_encoder", CrossEncoderReranker)

__all__ = ["CrossEncoderReranker"]
