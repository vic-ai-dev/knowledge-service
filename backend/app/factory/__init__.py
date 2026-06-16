"""Libs 可插拔层 -- 导入实现包以触发工厂注册。"""

# 导入 LLM 实现，触发 LLMFactory.register()
import app.factory.llm  # noqa: F401
import app.factory.embedding  # noqa: F401
import app.factory.splitter  # noqa: F401
import app.factory.loader  # noqa: F401
import app.factory.vector_store  # noqa: F401
import app.factory.reranker  # noqa: F401
import app.factory.evaluator  # noqa: F401

__all__: list[str] = []
