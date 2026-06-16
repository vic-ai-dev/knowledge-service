"""Embedding 实现包 -- 导入即触发工厂注册。"""

from app.factory.embedding.openai import OpenAIEmbedding
from app.factory.embedding.ollama import OllamaEmbedding
from app.factory.factory import EmbeddingFactory

# ── 注册默认实现 ────────────────────────────────────────────

# OpenAI-compatible（OpenAI, Azure 等）共用同一实现
EmbeddingFactory.register("openai", OpenAIEmbedding)
EmbeddingFactory.register("azure", OpenAIEmbedding)

# Ollama 本地后端
EmbeddingFactory.register("ollama", OllamaEmbedding)

__all__ = ["OpenAIEmbedding", "OllamaEmbedding"]
