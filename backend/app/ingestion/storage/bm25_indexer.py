"""C11 — BM25Indexer：PostgreSQL 全文检索（基于 tsvector + tsquery）。

使用 PostgreSQL 内置的全文检索能力（tsvector / tsquery / ts_rank_cd）
提供稀疏检索，数据直接复用 document_chunks 表中的 text 列，
该表的 text_search 列由 GENERATED ALWAYS AS (to_tsvector(...)) STORED 自动填充。

搜素和删除基于同一个 document_chunks 表，天然保证索引一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

import asyncpg

import jieba
from app.common.log import get_logger
from app.observability.instrumentation import trace_span

logger = get_logger(__name__)


@dataclass
class BM25SearchResult:
    """BM25 全文检索结果。"""
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None
    doc_id: str | None = None
    category: str | None = None
    language: str | None = None
    doc_type: str | None = None


class BM25IndexerError(RuntimeError):
    """BM25Indexer 通用异常。"""
    pass


class BM25Indexer:
    """PostgreSQL 全文检索索引器。

    通过 asyncpg 连接 knowledge_rag 库，在 document_chunks 表上执行
    tsvector 全文检索。tsvector 列由 GENERATED ALWAYS AS 自动维护，
    无需手动更新索引。

    :param host: PostgreSQL 主机地址。
    :param port: PostgreSQL 端口。
    :param user: PostgreSQL 用户名。
    :param password: PostgreSQL 密码。
    :param database: PostgreSQL 数据库名（默认 knowledge_rag）。
    :param table: 文档块表名（默认 document_chunks）。
    :param min_size: 连接池最小连接数。
    :param max_size: 连接池最大连接数。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "root123456",
        database: str = "knowledge_rag",
        table: str = "document_chunks",
        min_size: int = 2,
        max_size: int = 10,
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._table = table
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

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
                    min_size=self._min_size,
                    max_size=self._max_size,
                )
            except asyncpg.PostgresError as e:
                raise BM25IndexerError(
                    f"Failed to connect to PostgreSQL: {e}"
                ) from e
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ── 核心搜索方法 ──

    @staticmethod
    def _clean_cjk_query(query: str) -> str:
        """Clean CJK query for PostgreSQL tsvector search.

        PostgreSQL simple tokenization treats each CJK char as a separate
        lexeme, and plainto_tsquery ANDs them. Question particles like
        '是''什''么' that don't appear in docs cause zero matches.
        We use jieba to extract content words and return a cleaned string.
        """
        if not query:
            return query
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in query)
        if not has_cjk:
            return query

        STOP_WORDS = frozenset({
            '是', '什么', '怎么', '如何', '为什么', '哪些', '哪个', '哪', '谁',
            '吗', '呢', '吧', '的', '了', '在', '有', '和', '就', '都', '而',
            '及', '与', '着', '或', '被', '把', '对', '从', '让',
            '一个', '没有', '不是', '可以', '应该', '能够', '会', '要',
            '将', '已经', '正在', '更', '最', '很', '比较', '非常',
            '请问', '请教', '帮我', '告诉',
        })

        words = [w for w in jieba.lcut(query) if w.strip() and w not in STOP_WORDS]
        if not words:
            stop_chars = set(''.join(STOP_WORDS))
            chars = [c for c in query if '\u4e00' <= c <= '\u9fff' and c not in stop_chars]
            return ''.join(chars)
        return ''.join(words)

    @trace_span()
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        """执行全文检索。

        使用 plainto_tsquery 解析查询词，ts_rank_cd 计算相关度分数，
        支持通过 collection / category / language / doc_type / doc_id 过滤。

        Args:
            query: 搜索关键词（自然语言，无需查询语法）。
            top_k: 返回的最大结果数。
            filters: 可选过滤条件。

        Returns:
            排序后的 BM25 检索结果列表（按相关度降序）。

        Raises:
            BM25IndexerError: 检索过程中发生数据库错误。
        """
        if not query or not query.strip():
            return []

        pool = await self._get_pool()

        conditions: list[str] = [
            "text_search @@ plainto_tsquery('simple', $1)"
        ]
        cleaned = self._clean_cjk_query(query.strip())
        params: list[Any] = [cleaned]
        p = 2

        if filters:
            for key in ("category", "language", "doc_type"):
                val = filters.get(key)
                if val:
                    conditions.append(f"{key} = ${p}")
                    params.append(val)
                    p += 1
            if filters.get("doc_id"):
                conditions.append(f"doc_id = ${p}::uuid")
                params.append(str(filters["doc_id"]))
                p += 1

        where = " AND ".join(conditions)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT id, text, metadata, source_path, doc_id,
                           category, language, doc_type,
                           ts_rank_cd(text_search, plainto_tsquery('simple', $1), 32) AS score
                    FROM {self._table}
                    WHERE {where}
                    ORDER BY score DESC
                    LIMIT {top_k}
                    """,
                    *params,
                )
        except asyncpg.PostgresError as e:
            raise BM25IndexerError(f"BM25 search failed: {e}") from e

        return [
            BM25SearchResult(
                chunk_id=str(r["id"]),
                text=r["text"],
                score=float(r["score"]),
                metadata=self._parse_metadata(r.get("metadata")),
                source_path=r.get("source_path"),
                doc_id=str(r["doc_id"]) if r.get("doc_id") else None,
                category=r.get("category"),
                language=r.get("language"),
                doc_type=r.get("doc_type"),
            )
            for r in rows
        ]

    # ── 工具方法 ──

    @staticmethod
    def _parse_metadata(raw: Any) -> dict:
        """将 asyncpg 返回的 JSONB 值安全转换为 dict。"""
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return dict(raw)  # shallow copy
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    # ── 删除方法 ──

    @trace_span()
    async def delete_by_doc_id(self, doc_id: str) -> int:
        """按文档 ID 删除全文检索索引记录。

        Args:
            doc_id: 文档 UUID。

        Returns:
            删除的记录数。
        """
        pool = await self._get_pool()
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    f"DELETE FROM {self._table} WHERE doc_id = $1::uuid",
                    str(doc_id),
                )
        except asyncpg.PostgresError as e:
            raise BM25IndexerError(
                f"Failed to delete by doc_id: {e}"
            ) from e
        parts = result.split()
        return int(parts[-1]) if len(parts) > 1 else 0

    @trace_span()
    async def delete(self, chunk_ids: list[str]) -> int:
        """按 chunk_id 列表删除全文检索索引记录。

        Args:
            chunk_ids: 要删除的 chunk ID 列表。

        Returns:
            删除的记录数。
        """
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
            raise BM25IndexerError(
                f"Failed to delete chunks: {e}"
            ) from e
        parts = result.split()
        return int(parts[-1]) if len(parts) > 1 else 0


__all__ = ["BM25Indexer", "BM25SearchResult", "BM25IndexerError"]
