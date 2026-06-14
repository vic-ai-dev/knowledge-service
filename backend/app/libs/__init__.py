"""Libs 可插拔层 -- 导入实现包以触发工厂注册。"""

# 导入 LLM 实现，触发 LLMFactory.register()
import app.libs.llm  # noqa: F401
import app.libs.embedding  # noqa: F401
import app.libs.splitter  # noqa: F401
import app.libs.vector_store  # noqa: F401
import app.libs.reranker  # noqa: F401
import app.libs.evaluator  # noqa: F401

__all__: list[str] = []
