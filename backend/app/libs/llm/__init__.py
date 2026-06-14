"""LLM 实现包 -- 导入即触发工厂注册。"""

from app.libs.llm.openai import OpenAILLM
from app.libs.llm.ollama import OllamaLLM
from app.libs.llm.deepseek import DeepSeekLLM
from app.libs.factory import LLMFactory

# ── 注册默认实现 ────────────────────────────────────────────

# OpenAI-compatible (OpenAI, Azure 等) 共用同一实现
LLMFactory.register("openai", OpenAILLM)
LLMFactory.register("azure", OpenAILLM)

# DeepSeek 专用实现（支持 reasoning_content 及扩展 usage）
LLMFactory.register("deepseek", DeepSeekLLM)

# Ollama 本地后端
LLMFactory.register("ollama", OllamaLLM)

__all__ = ["OpenAILLM", "OllamaLLM", "DeepSeekLLM"]
