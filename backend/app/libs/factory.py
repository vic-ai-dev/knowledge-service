"""工厂层 — 配置驱动的可插拔抽象工厂。"""

from __future__ import annotations

from typing import Any

from app.core.settings import Settings, get_settings


def _config_kwargs(
    cfg: Any,
    exclude: tuple[str, ...] = ("provider", "model"),
) -> dict[str, Any]:
    """从配置模型中提取 exclude 之外的所有字段作为 kwargs。"""
    return cfg.model_dump(exclude=set(exclude))


# ── LLM ─────────────────────────────────────────────────
from app.libs.base.base_llm import BaseLLM


class LLMFactory:
    """LLM 工厂。"""

    _registry: dict[str, type[BaseLLM]] = {}

    @classmethod
    def register(cls, provider: str, impl: type[BaseLLM]) -> None:
        cls._registry[provider] = impl

    @classmethod
    def create(cls, provider: str | None = None, model: str | None = None, **kwargs) -> BaseLLM:
        settings = get_settings()
        provider = provider or settings.llm.provider
        model = model or settings.llm.model
        merged = {**_config_kwargs(settings.llm), **kwargs}
        impl_cls = cls._registry.get(provider)
        if impl_cls is None:
            raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(cls._registry.keys())}")
        return impl_cls(model=model, **merged)


# ── Embedding ───────────────────────────────────────────
from app.libs.base.base_embedding import BaseEmbedding


class EmbeddingFactory:
    """Embedding 工厂。"""

    _registry: dict[str, type[BaseEmbedding]] = {}

    @classmethod
    def register(cls, provider: str, impl: type[BaseEmbedding]) -> None:
        cls._registry[provider] = impl

    @classmethod
    def create(cls, provider: str | None = None, model: str | None = None, **kwargs) -> BaseEmbedding:
        settings = get_settings()
        provider = provider or settings.embedding.provider
        model = model or settings.embedding.model
        merged = {**_config_kwargs(settings.embedding), **kwargs}
        impl_cls = cls._registry.get(provider)
        if impl_cls is None:
            raise ValueError(f"Unknown Embedding provider: {provider}. Available: {list(cls._registry.keys())}")
        return impl_cls(model=model, **merged)


# ── Splitter ────────────────────────────────────────────
from app.libs.base.base_splitter import BaseSplitter


class SplitterFactory:
    """Splitter 工厂（按文件类型路由）。"""

    _registry: dict[str, type[BaseSplitter]] = {}

    @classmethod
    def register(cls, splitter_type: str, impl: type[BaseSplitter]) -> None:
        cls._registry[splitter_type] = impl

    @classmethod
    def create(cls, splitter_type: str, **kwargs) -> BaseSplitter:
        impl_cls = cls._registry.get(splitter_type)
        if impl_cls is None:
            raise ValueError(f"Unknown Splitter type: {splitter_type}. Available: {list(cls._registry.keys())}")
        return impl_cls(**kwargs)

    @classmethod
    def create_for_doc_type(
        cls, doc_type: str, settings: Settings | None = None
    ) -> BaseSplitter:
        """根据文档类型自动选择分块策略。"""
        cfg = (settings or get_settings()).splitter
        if doc_type == "md":
            return cls.create("markdown_header", **cfg.markdown.model_dump())
        elif doc_type == "html":
            return cls.create("html_header", **cfg.html.model_dump())
        else:
            return cls.create("recursive_character", **cfg.default.model_dump())


# ── VectorStore ─────────────────────────────────────────
from app.libs.base.base_vector_store import BaseVectorStore


class VectorStoreFactory:
    """VectorStore 工厂。"""

    _registry: dict[str, type[BaseVectorStore]] = {}

    @classmethod
    def register(cls, backend: str, impl: type[BaseVectorStore]) -> None:
        cls._registry[backend] = impl

    @classmethod
    def create(cls, backend: str | None = None, **kwargs) -> BaseVectorStore:
        settings = get_settings()
        backend = backend or settings.vector_store.backend
        impl_cls = cls._registry.get(backend)
        if impl_cls is None:
            raise ValueError(f"Unknown VectorStore backend: {backend}. Available: {list(cls._registry.keys())}")
        return impl_cls(**kwargs)


# ── Reranker ────────────────────────────────────────────
from app.libs.base.base_reranker import BaseReranker


class RerankerFactory:
    """Reranker 工厂（含 None 回退）。"""

    _registry: dict[str, type[BaseReranker]] = {}

    @classmethod
    def register(cls, backend: str, impl: type[BaseReranker]) -> None:
        cls._registry[backend] = impl

    @classmethod
    def create(cls, backend: str | None = None, **kwargs) -> BaseReranker:
        settings = get_settings()
        backend = backend or settings.retrieval.rerank_backend
        if backend == "none":
            from app.libs.base.base_reranker import NoOpReranker
            return NoOpReranker()
        merged = {**_config_kwargs(settings.rerank), **kwargs}
        impl_cls = cls._registry.get(backend)
        if impl_cls is None:
            raise ValueError(f"Unknown Reranker backend: {backend}. Available: {list(cls._registry.keys())}")
        return impl_cls(**merged)


# ── Evaluator ───────────────────────────────────────────
from app.libs.base.base_evaluator import BaseEvaluator


class EvaluatorFactory:
    """Evaluator 工厂。"""

    _registry: dict[str, type[BaseEvaluator]] = {}

    @classmethod
    def register(cls, name: str, impl: type[BaseEvaluator]) -> None:
        cls._registry[name] = impl

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseEvaluator:
        impl_cls = cls._registry.get(name)
        if impl_cls is None:
            raise ValueError(f"Unknown Evaluator: {name}. Available: {list(cls._registry.keys())}")
        return impl_cls(**kwargs)


# ── Loader ──────────────────────────────────────────────
from app.libs.base.base_loader import BaseLoader


class LoaderFactory:
    """Loader 工厂。"""

    _registry: dict[str, type[BaseLoader]] = {}

    @classmethod
    def register(cls, doc_type: str, impl: type[BaseLoader]) -> None:
        cls._registry[doc_type] = impl

    @classmethod
    def create(cls, doc_type: str, **kwargs) -> BaseLoader:
        impl_cls = cls._registry.get(doc_type)
        if impl_cls is None:
            raise ValueError(f"Unknown Loader for doc_type: {doc_type}. Available: {list(cls._registry.keys())}")
        return impl_cls(**kwargs)
# ── Evaluator 注册 ──
from app.libs.evaluator.basic import BasicEvaluator
from app.libs.evaluator.ragas_evaluator import RagasEvaluator
from app.libs.evaluator.composite import CompositeEvaluator
EvaluatorFactory.register("basic", BasicEvaluator)
EvaluatorFactory.register("ragas", RagasEvaluator)
EvaluatorFactory.register("composite", CompositeEvaluator)
