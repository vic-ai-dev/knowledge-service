"""Libs 可插拔层 -- 导入实现包以触发工厂注册。"""

# 导入 LLM 实现，触发 LLMFactory.register()
import app.libs.llm  # noqa: F401

__all__: list[str] = []
