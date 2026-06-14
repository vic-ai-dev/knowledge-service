"""系统配置加载与校验。

配置优先级（从低到高）：
  1. config/settings.yaml（默认配置）
  2. KS_* 环境变量覆盖
"""

from pathlib import Path
from typing import Annotated, List, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


# ── 嵌套配置模型 ──────────────────────────────────────────────

class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "root123456"
    database: str = "knowledge"
    max_connections: int = 10

    @field_validator("port")
    @classmethod
    def check_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError(f"port 必须在 1–65535 范围内，得到 {v}")
        return v

    @field_validator("max_connections")
    @classmethod
    def check_max_connections(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"max_connections 必须 >= 1，得到 {v}")
        return v


class VectorStoreConfig(BaseModel):
    backend: str = "pgvector"
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "root123456"
    database: str = "knowledge_rag"
    table_name: str = "document_chunks"
    embedding_dimensions: int = 1536

    @field_validator("port")
    @classmethod
    def check_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError(f"port 必须在 1–65535 范围内，得到 {v}")
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def check_embedding_dims(cls, v: int) -> int:
        if v not in (384, 512, 768, 1024, 1536, 3072):
            raise ValueError(
                f"embedding_dimensions 必须为常用值之一 (384/512/768/1024/1536/3072)，得到 {v}"
            )
        return v


class LLMConfig(BaseModel):
    provider: Literal["azure", "openai", "ollama", "deepseek"] = "azure"
    model: str = "gpt-4o"


class EmbeddingConfig(BaseModel):
    provider: Literal["openai", "azure", "ollama"] = "openai"
    model: str = "text-embedding-3-small"


class SplitterStrategy(BaseModel):
    type: str = "recursive_character"
    headers_to_split_on: list = []
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] | None = None

    @field_validator("chunk_size")
    @classmethod
    def check_chunk_size(cls, v: int) -> int:
        if v < 100:
            raise ValueError(f"chunk_size 必须 >= 100，得到 {v}")
        return v

    @model_validator(mode="after")
    def check_overlap_less_than_chunk(self) -> "SplitterStrategy":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) 必须小于 chunk_size ({self.chunk_size})"
            )
        return self


class SplitterConfig(BaseModel):
    markdown: SplitterStrategy = SplitterStrategy(
        type="markdown_header",
        headers_to_split_on=[["#", "h1"], ["##", "h2"], ["###", "h3"]],
    )
    html: SplitterStrategy = SplitterStrategy(
        type="html_header",
        headers_to_split_on=[["h1", "h1"], ["h2", "h2"], ["h3", "h3"]],
    )
    default: SplitterStrategy = SplitterStrategy(
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
    )


class RetrievalConfig(BaseModel):
    sparse_backend: str = "pg_bm25"
    fusion_algorithm: str = "rrf"
    rerank_backend: Literal["none", "cross_encoder", "llm"] = "cross_encoder"


class SparseSearchConfig(BaseModel):
    backend: str = "pg_bm25"  # pg_bm25 | elasticsearch
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "root123456"
    database: str = "knowledge_rag"


class EvaluationConfig(BaseModel):
    backends: list[str] = ["ragas", "custom_metrics"]


class LoggingConfig(BaseModel):
    log_file: str = "logs/service.jsonl"
    log_level: str = "INFO"
    service_name: str = "knowledge_service"


class ObservabilityConfig(BaseModel):
    enabled: bool = True
    logging: LoggingConfig = LoggingConfig()


class ServerConfig(BaseModel):
    port: int = 8000
    reload: bool = False
    max_file_size: int = 52_428_800  # 50MB
    allowed_extensions: list[str] = ["pdf", "md", "html"]

    @field_validator("port")
    @classmethod
    def check_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError(f"port 必须在 1–65535 范围内，得到 {v}")
        return v

    @field_validator("max_file_size")
    @classmethod
    def check_max_file_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_file_size 必须 > 0，得到 {v}")
        return v


# ── 主配置 ───────────────────────────────────────────────────

class Settings(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    llm: LLMConfig = LLMConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    splitter: SplitterConfig = SplitterConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    sparse_search: SparseSearchConfig = SparseSearchConfig()
    evaluation: EvaluationConfig = EvaluationConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    server: ServerConfig = ServerConfig()

    model_config = {"env_prefix": "KS_", "env_nested_delimiter": "__"}

    @classmethod
    def from_yaml(cls, path: str | Path = "config/settings.yaml") -> "Settings":
        """从 YAML 文件加载配置，并与环境变量覆盖合并。"""
        path = Path(path)
        if not path.is_absolute():
            candidates = [
                path,
                Path.cwd() / path,
                Path(__file__).resolve().parent.parent.parent / path,
            ]
            for candidate in candidates:
                if candidate.is_file():
                    path = candidate
                    break
            else:
                return cls()

        if not path.is_file():
            return cls()

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        mapping = {
            "database": "database",
            "vector_store": "vector_store",
            "llm": "llm",
            "embedding": "embedding",
            "splitter": "splitter",
            "retrieval": "retrieval",
            "sparse_search": "sparse_search",
            "evaluation": "evaluation",
            "observability": "observability",
            "server": "server",
        }
        kwargs = {}
        for yaml_key, model_attr in mapping.items():
            if yaml_key in raw:
                kwargs[model_attr] = raw[yaml_key]

        return cls(**kwargs)


# ── 全局单例 ─────────────────────────────────────────────────

_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局 Settings 实例（惰性加载）。"""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml()
    return _settings
