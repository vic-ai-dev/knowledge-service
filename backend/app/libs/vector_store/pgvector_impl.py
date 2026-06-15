"""
PGVector 向量存储实现（asyncpg + pgvector）。

Connects to the configured PostgreSQL database with pgvector extension.
Uses cosine distance (<=>) for vector similarity search.

安全考量：
- 表名通过 _validate_table_name() 校验，防止 SQL 注入
- asyncpg 连接/查询异常统一包装为 VectorStoreError
- 输入参数均经过非空校验
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import asyncpg

from app.libs.base.base_vector_store import BaseVectorStore, VectorSearchResult
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)

# 仅允许字母、数字、下划线的表名
_VALID_TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


class VectorStoreError(RuntimeError):
    """VectorStore 操作异常。"""
    pass


class PGVectorStore(BaseVectorStore):
    """基于 PostgreSQL + pgvector 的向量存储实现。

    Connection parameters come from VectorStoreConfig:
        host, port, user, password, database, table_name, embedding_dimensions
    """

    def __init__(self, **kwargs: Any):
        self._host = kwargs.get("host", "localhost")
        self._port = kwargs.get("port", 5432)
        self._user = kwargs.get("user", "postgres")
        self._password = kwargs.get("password", "root123456")
        self._database = kwargs.get("database", "knowledge_rag")
        self._table = kwargs.get("table_name", "document_chunks")
        self._embedding_dims = kwargs.get("embedding_dimensions", 1536)
        self._pool: asyncpg.Pool | None = None
        self._validate_table_name()

    # ── 安全校验 ──

    def _validate_table_name(self) -> None:
        """校验表名合法性，防止 SQL 注入。"""
        if not _VALID_TABLE_NAME_RE.match(str(self._table)):
            raise VectorStoreError(
                f"Invalid table name: '{self._table}'. "
                f"Only alphanumeric and underscore allowed (max 64 chars)."
            )

    # ── 连接管理 ──

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    host=self._host,
                    port=self._port,
                    user=self._user,
                    password=self._password,
                    database=self._database,
                    min_size=2,
                    max_size=10,
                )
            except asyncpg.PostgresError as e:
                raise VectorStoreError(
                    f"Failed to connect to PostgreSQL: {e}"
                ) from e
        return self._pool

    def _vec_str(self, embedding: list[float]) -> str:
        """将 float list 转为 pgvector 文本表示。"""
        return "[" + ",".join(str(x) for x in embedding) + "]"

    # ── 输入校验 ──

    def _validate_embedding(self, embedding: list[float]) -> None:
        if not embedding:
            raise VectorStoreError("embedding vector cannot be empty")

    def _validate_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            raise VectorStoreError("chunks list cannot be empty")

    # ── BaseVectorStore 接口实现 ──

    @trace_span(span_name="upsert")
    async def upsert(self, chunks: list[dict]) -> int:
        """批量写入 / 更新向量。"""
        self._validate_chunks(chunks)
        pool = await self._get_pool()
        count = 0
        async with pool.acquire() as conn:
            for chunk in chunks:
                chunk_id = chunk.get("id", str(uuid.uuid4()))
                embedding = chunk.get("embedding")
                emb_str = self._vec_str(embedding) if embedding else None

                try:
                    await conn.execute(
                        f"""
                        INSERT INTO {self._table}
                            (id, text, metadata, collection, category, language,
                             doc_type, doc_id, chunk_index, source_path, token_count,
                             embedding)
                        VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9, $10, $11,
                                $12::vector)
                        ON CONFLICT (id) DO UPDATE SET
                            text        = EXCLUDED.text,
                            metadata    = EXCLUDED.metadata,
                            embedding   = EXCLUDED.embedding,
                            updated_at  = NOW()
                        """,
                        str(chunk_id),
                        chunk.get("text", ""),
                        json.dumps(chunk.get("metadata", {}) or {}),
                        chunk.get("collection", "default"),
                        chunk.get("category"),
                        chunk.get("language"),
                        chunk.get("doc_type"),
                        str(chunk["doc_id"]) if chunk.get("doc_id") else None,
                        chunk.get("chunk_index"),
                        chunk.get("source_path"),
                        chunk.get("token_count", 0),
                        emb_str,
                    )
                except asyncpg.PostgresError as e:
                    raise VectorStoreError(
                        f"Failed to upsert chunk {chunk_id}: {e}"
                    ) from e
                count += 1
        return count

    @trace_span(span_name="query")
    async def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
        **kwargs: Any,
    ) -> list[VectorSearchResult]:
        """向量余弦相似度检索。"""
        self._validate_embedding(embedding)
        pool = await self._get_pool()
        emb_str = self._vec_str(embedding)

        conditions: list[str] = []
        params: list[Any] = []
        p = 1

        if filters:
            for key in ("collection", "category", "language", "doc_type"):
                val = filters.get(key)
                if val:
                    conditions.append(f"{key} = ${p}")
                    params.append(val)
                    p += 1
            if filters.get("doc_id"):
                conditions.append(f"doc_id = ${p}::uuid")
                params.append(str(filters["doc_id"]))
                p += 1

        where = " AND ".join(conditions) if conditions else "TRUE"

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT id, text, metadata, source_path,
                           1 - (embedding <=> ${p}::vector) AS score
                    FROM {self._table}
                    WHERE {where}
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> ${p}::vector
                    LIMIT {top_k}
                    """,
                    *params,
                    emb_str,
                )
        except asyncpg.PostgresError as e:
            raise VectorStoreError(
                f"Vector query failed: {e}"
            ) from e

        return [
            VectorSearchResult(
                chunk_id=str(r["id"]),
                text=r["text"],
                metadata=dict(r["metadata"]) if r.get("metadata") else {},
                score=float(r["score"]),
                source_path=r.get("source_path"),
            )
            for r in rows
        ]

    @trace_span(span_name="delete")
    async def delete(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        pool = await self._get_pool()
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    f"DELETE FROM {self._table} WHERE id = ANY($1::uuid[])",
                    [str(cid) for cid in chunk_ids],
                )
        except asyncpg.PostgresError as e:
            raise VectorStoreError(
                f"Failed to delete chunks: {e}"
            ) from e
        parts = result.split()
        return int(parts[-1]) if len(parts) > 1 else 0

    @trace_span(span_name="delete_by_doc_id")
    async def delete_by_doc_id(self, doc_id: str) -> int:
        pool = await self._get_pool()
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    f"DELETE FROM {self._table} WHERE doc_id = $1::uuid",
                    str(doc_id),
                )
        except asyncpg.PostgresError as e:
            raise VectorStoreError(
                f"Failed to delete by doc_id: {e}"
            ) from e
        parts = result.split()
        return int(parts[-1]) if len(parts) > 1 else 0

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
