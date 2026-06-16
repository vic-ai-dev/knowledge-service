"""BM25Indexer — 倒排索引 + 磁盘持久化（参考 MODULAR-RAG-MCP-SERVER 实现）。

使用 jieba 分词，自实现 BM25 公式构建倒排索引，持久化到磁盘 JSON 文件。
支持增量更新（add_documents / remove_document）和懒加载。

设计要点：
  - 持久化：索引保存为 JSON 文件到 data/bm25/ 目录，原子写入
  - 增量更新：add_documents() 合并新块后重建 IDF
  - 懒加载：首次 search() 时自动从磁盘加载
  - 无外部依赖：自实现 BM25 公式
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jieba

from app.common.log import get_logger

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
    """倒排索引 + 磁盘持久化 BM25 检索器。

    从 chunk 文本提取词频，构建 term -> {idf, df, postings} 倒排索引，
    用自实现 BM25 公式评分，持久化到磁盘 JSON 文件。

    :param index_dir: 索引文件存储目录（相对路径基于项目根目录 backend/）。
    :param k1: BM25 词频饱和参数。
    :param b: BM25 长度归一化参数。
    """

    # 项目根目录 = bm25_indexer.py 向上 4 级: storage -> ingestion -> app -> backend
    _BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent

    def __init__(
        self,
        index_dir: str | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        if index_dir is None:
            index_dir = str(self._BACKEND_ROOT / "data" / "bm25")
        self.index_dir = Path(index_dir)
        self.k1 = k1
        self.b = b

        self._metadata: dict[str, Any] = {}
        self._index: dict[str, dict[str, Any]] = {}
        self._documents: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._last_load_mtime: float = 0.0

    # ── 分词 ──────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """jieba 分词，过滤短词和空白符。"""
        if not text:
            return []
        tokens = jieba.lcut(text)
        return [w.lower() for w in tokens if len(w.strip()) >= 2]

    # ── 词频提取 ──────────────────────────────────────────

    @staticmethod
    def compute_term_stats(text: str) -> tuple[dict[str, int], int]:
        """从文本提取词频统计。

        Returns:
            (term_frequencies, doc_length)
        """
        tokens = BM25Indexer._tokenize(text)
        freqs: dict[str, int] = {}
        for t in tokens:
            freqs[t] = freqs.get(t, 0) + 1
        return freqs, len(tokens)

    # ── BM25 计算 ─────────────────────────────────────────

    def _calculate_idf(self, num_docs: int, df: int) -> float:
        return math.log((num_docs - df + 0.5) / (df + 0.5))

    def _calculate_bm25_score(
        self, tf: int, doc_length: int, avg_doc_length: float, idf: float
    ) -> float:
        if avg_doc_length == 0:
            avg_doc_length = 1.0
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))
        return idf * (numerator / denominator)

    # ── 构建 ──────────────────────────────────────────────

    async def build(self, term_stats: list[dict[str, Any]], collection: str = "default") -> None:
        """从 term 统计重建完整索引。

        term_stats 每项格式:
            {"chunk_id": str, "term_frequencies": dict, "doc_length": int}
        """
        if not term_stats:
            raise BM25IndexerError("Cannot build index from empty term_stats")
        self._validate_term_stats(term_stats)

        num_docs = len(term_stats)
        total_length = sum(s["doc_length"] for s in term_stats)
        avg_doc_length = total_length / num_docs if num_docs > 0 else 0.0

        doc_freq: dict[str, int] = {}
        for stat in term_stats:
            for term in stat["term_frequencies"]:
                doc_freq[term] = doc_freq.get(term, 0) + 1

        index: dict[str, dict[str, Any]] = {}
        for term, df in doc_freq.items():
            idf = self._calculate_idf(num_docs, df)
            postings = []
            for stat in term_stats:
                tf = stat["term_frequencies"].get(term, 0)
                if tf > 0:
                    postings.append({
                        "chunk_id": stat["chunk_id"],
                        "tf": tf,
                        "doc_length": stat["doc_length"],
                    })
            index[term] = {"idf": idf, "df": df, "postings": postings}

        self._metadata = {
            "num_docs": num_docs,
            "avg_doc_length": avg_doc_length,
            "total_terms": len(index),
            "collection": collection,
        }
        self._index = index
        await self._save(collection)
        self._loaded = True

        logger.info("bm25_rebuild_done", metadata={"chunks": num_docs, "terms": len(index)})

    # ── 持久化 ────────────────────────────────────────────

    def _get_index_path(self, collection: str = "default") -> Path:
        return self.index_dir / f"{collection}_bm25.json"

    async def _save(self, collection: str = "default") -> None:
        """原子写入索引到磁盘（异步）。"""
        import asyncio
        self.index_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_index_path(collection)
        temp_path = path.with_suffix(".tmp")
        data = {
            "metadata": self._metadata,
            "documents": self._documents,
            "index": self._index,
        }
        loop = asyncio.get_running_loop()

        def _write():
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(path)

        try:
            await loop.run_in_executor(None, _write)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise BM25IndexerError(f"Failed to save index: {e}") from e

    async def load(self, collection: str = "default") -> bool:
        """从磁盘加载索引（异步）。"""
        import asyncio
        path = self._get_index_path(collection)
        if not path.exists():
            return False
        loop = asyncio.get_running_loop()

        def _read():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            data = await loop.run_in_executor(None, _read)
            if "metadata" not in data or "index" not in data:
                raise BM25IndexerError("Invalid index file structure")
            self._metadata = data["metadata"]
            self._index = data["index"]
            self._documents = data.get("documents", {})
            self._loaded = True
            self._last_load_mtime = path.stat().st_mtime
            logger.info("bm25_loaded", metadata={"chunks": self._metadata.get("num_docs", 0)})
            return True
        except json.JSONDecodeError as e:
            raise BM25IndexerError(f"Corrupted index file: {e}") from e

    # ── 增量更新 ──────────────────────────────────────────

    async def add_documents(
        self,
        chunks: list[dict[str, Any]],
        doc_id: str | None = None,
        collection: str = "default",
    ) -> None:
        """增量添加文档块到 BM25 索引。

        chunks 每项格式:
            {"chunk_id": str, "text": str, "source_path": str, "doc_id": str,
             "category": str, "language": str, "doc_type": str, "metadata": dict}
        """
        if not chunks:
            return
        if not self._loaded:
            await self.load(collection)

        # 计算 term stats
        term_stats = []
        for ch in chunks:
            freqs, doc_len = self.compute_term_stats(ch["text"])
            term_stats.append({
                "chunk_id": ch["chunk_id"],
                "term_frequencies": freqs,
                "doc_length": doc_len,
            })
            self._documents[ch["chunk_id"]] = {
                "chunk_id": ch["chunk_id"],
                "text": ch["text"],
                "metadata": ch.get("metadata", {}),
                "source_path": ch.get("source_path"),
                "doc_id": ch.get("doc_id"),
                "category": ch.get("category"),
                "language": ch.get("language"),
                "doc_type": ch.get("doc_type"),
            }

        if doc_id:
            self._remove_document_internal(doc_id)

        existing = self._existing_stats_from_index(doc_id_to_skip=doc_id if doc_id else None)
        all_stats = existing + term_stats
        if all_stats:
            await self.build(all_stats, collection)
            # 恢复 documents（build 重建了 index 但丢了 text 信息，需要重新注册）
            for ch in chunks:
                self._documents[ch["chunk_id"]] = {
                    "chunk_id": ch["chunk_id"],
                    "text": ch["text"],
                    "metadata": ch.get("metadata", {}),
                    "source_path": ch.get("source_path"),
                    "doc_id": ch.get("doc_id"),
                    "category": ch.get("category"),
                    "language": ch.get("language"),
                    "doc_type": ch.get("doc_type"),
                }

        logger.info("bm25_add_documents", metadata={"chunks": len(chunks), "doc_id": doc_id})

    def _existing_stats_from_index(
        self, doc_id_to_skip: str | None = None
    ) -> list[dict[str, Any]]:
        """从当前倒排索引重建 term_stats（用于合并保留旧数据）。"""
        stats_map: dict[str, dict[str, Any]] = {}
        for term, term_data in self._index.items():
            for posting in term_data["postings"]:
                cid = posting["chunk_id"]
                if doc_id_to_skip and cid.startswith(doc_id_to_skip):
                    continue
                if cid not in stats_map:
                    stats_map[cid] = {
                        "chunk_id": cid,
                        "term_frequencies": {},
                        "doc_length": posting["doc_length"],
                    }
                stats_map[cid]["term_frequencies"][term] = posting["tf"]
        return list(stats_map.values())

    def _remove_document_internal(self, doc_id: str) -> bool:
        """内部：从内存 index/documents 移除文档，不持久化。"""
        if not self._index:
            return False

        # 通过 _documents 映射查找属于该 doc_id 的 chunk_ids
        chunk_ids_to_remove = {
            cid for cid, d in self._documents.items()
            if d.get("doc_id") == doc_id
        }
        if not chunk_ids_to_remove:
            return False

        removed_any = False
        terms_to_delete = []
        for term, term_data in self._index.items():
            original_len = len(term_data["postings"])
            term_data["postings"] = [
                p for p in term_data["postings"]
                if p["chunk_id"] not in chunk_ids_to_remove
            ]
            if len(term_data["postings"]) < original_len:
                removed_any = True
            if not term_data["postings"]:
                terms_to_delete.append(term)
            else:
                term_data["df"] = len(term_data["postings"])

        for term in terms_to_delete:
            del self._index[term]

        self._documents = {
            cid: d for cid, d in self._documents.items()
            if d.get("doc_id") != doc_id
        }

        if removed_any:
            all_chunk_ids = set()
            total_length = 0
            for td in self._index.values():
                for p in td["postings"]:
                    all_chunk_ids.add(p["chunk_id"])
                    total_length += p["doc_length"]
            num_docs = len(all_chunk_ids)
            avg_doc_length = total_length / num_docs if num_docs else 0.0
            for td in self._index.values():
                td["idf"] = self._calculate_idf(num_docs, td["df"])
            self._metadata.update({
                "num_docs": num_docs,
                "avg_doc_length": avg_doc_length,
                "total_terms": len(self._index),
            })
        return removed_any

    async def remove_document(self, doc_id: str, collection: str = "default") -> bool:
        """从 BM25 索引移除文档的所有块。"""
        if not self._loaded:
            if not await self.load(collection):
                return False
        result = self._remove_document_internal(doc_id)
        if result:
            await self._save(collection)
            logger.info("bm25_remove_document", metadata={"doc_id": doc_id})
        return result

    # ── 搜索 ──────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        """执行 BM25 全文检索。"""
        if not query or not query.strip():
            return []

        if not self._loaded:
            await self.load()

        # 自动检测磁盘文件变更（ingestion 异步写入后触发重载）
        index_path = self._get_index_path()
        if self._loaded and self._last_load_mtime > 0 and index_path.exists():
            current_mtime = index_path.stat().st_mtime
            if current_mtime > self._last_load_mtime:
                self._loaded = False
                self._index = {}
                self._documents = {}
                await self.load()

        if not self._index:
            return []

        query_terms = self._tokenize(query.strip())
        if not query_terms:
            return []

        scores: dict[str, float] = {}
        avg_dl = self._metadata.get("avg_doc_length", 1.0)

        for term in query_terms:
            t = term.lower()
            if t not in self._index:
                continue
            td = self._index[t]
            idf = td["idf"]
            for posting in td["postings"]:
                cid = posting["chunk_id"]
                score = self._calculate_bm25_score(
                    tf=posting["tf"],
                    doc_length=posting["doc_length"],
                    avg_doc_length=avg_dl,
                    idf=idf,
                )
                scores[cid] = scores.get(cid, 0.0) + score

        results: list[BM25SearchResult] = []
        for cid, score in sorted(scores.items(), key=lambda x: -x[1]):
            doc = self._documents.get(cid, {})
            if filters:
                skip = False
                for key in ("category", "language", "doc_type"):
                    val = filters.get(key)
                    if val and doc.get(key) != val:
                        skip = True
                        break
                if filters.get("doc_id") and doc.get("doc_id") != str(filters["doc_id"]):
                    skip = True
                if skip:
                    continue
            results.append(BM25SearchResult(
                chunk_id=cid,
                text=doc.get("text", ""),
                score=float(score),
                metadata=doc.get("metadata", {}),
                source_path=doc.get("source_path"),
                doc_id=doc.get("doc_id"),
                category=doc.get("category"),
                language=doc.get("language"),
                doc_type=doc.get("doc_type"),
            ))
            if len(results) >= top_k:
                break

        return results

    # ── 校验 ──────────────────────────────────────────────

    @staticmethod
    def _validate_term_stats(term_stats: list[dict[str, Any]]) -> None:
        for i, stat in enumerate(term_stats):
            if not isinstance(stat, dict):
                raise BM25IndexerError(f"term_stats[{i}] must be a dict")
            for field in ("chunk_id", "term_frequencies", "doc_length"):
                if field not in stat:
                    raise BM25IndexerError(f"term_stats[{i}] missing field: {field}")

    # ── 维护 ──────────────────────────────────────────────

    def close(self) -> None:
        """释放内存。"""
        self._index.clear()
        self._documents.clear()
        self._metadata.clear()
        self._loaded = False

    async def rebuild(self) -> None:
        """强制重建索引（从磁盘重新加载）。"""
        self._loaded = False
        self._index.clear()
        self._documents.clear()
        if await self.load():
            logger.info("bm25_rebuilt", metadata={"chunks": self._metadata.get("num_docs", 0)})


__all__ = ["BM25Indexer", "BM25SearchResult", "BM25IndexerError"]
