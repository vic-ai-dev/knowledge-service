"""E14 — 查询与嵌入缓存层。

QueryCache   — LRU + TTL 缓存，缓存查询结果
EmbeddingCache — TTL + LRU 缓存，缓存嵌入向量

所有缓存均支持定期清理过期条目 (cleanup)，
与 FastAPI 的 lifespan 集成，在后台协程中运行。
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Optional

from app.common.log import get_logger

logger = get_logger(__name__)


class TTLCache:
    """通用 TTL + LRU 缓存基类。

    参数:
        max_size: 最大缓存条目数（超限淘汰最久未访问的条目）
        default_ttl: 默认存活时间（秒）
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        # OrderedDict: key -> (value, expiry_timestamp)
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    # ── 公共 API ─────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """获取缓存条目。已过期或不存在返回 None。"""
        if key not in self._cache:
            return None
        value, expiry = self._cache[key]
        if time.monotonic() > expiry:
            del self._cache[key]
            return None
        # LRU: 移到末尾表示最近使用
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存条目。"""
        if ttl is None:
            ttl = self._default_ttl
        expiry = time.monotonic() + ttl
        self._cache[key] = (value, expiry)
        self._cache.move_to_end(key)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        """删除指定 key。"""
        self._cache.pop(key, None)

    # ── 内部方法 ─────────────────────────────────────────

    def _evict_if_needed(self) -> None:
        """超出 max_size 时淘汰最久未访问的条目。"""
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    # ── 维护 ─────────────────────────────────────────────

    def cleanup(self) -> int:
        """清理所有过期条目。返回清理数量。"""
        now = time.monotonic()
        expired = [k for k, (_, e) in self._cache.items() if now > e]
        for k in expired:
            del self._cache[k]
        if expired:
            logger.debug(
                "cache_cleanup",
                message=f"清理了 {len(expired)} 条过期缓存",
                metadata={"expired_count": len(expired), "remaining": self.size},
            )
        return len(expired)

    def clear(self) -> None:
        """清空所有缓存。"""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class QueryCache(TTLCache):
    """查询结果缓存。

    默认 600 秒 TTL，最多 500 条。
    缓存 key 由 query_text + search_mode + filters 组合生成。
    """

    def __init__(self, max_size: int = 500, default_ttl: float = 600.0) -> None:
        super().__init__(max_size=max_size, default_ttl=default_ttl)

    @staticmethod
    def make_key(
        query_text: str,
        search_mode: str = "hybrid",
    ) -> str:
        """生成缓存 key（基于 query 的哈希）。"""
        return f"{query_text.strip().lower()}:{search_mode}"


class EmbeddingCache(TTLCache):
    """嵌入向量缓存。

    默认 3600 秒 TTL（1 小时），最多 2000 条。
    缓存 key 由 model + text 组合生成。
    """

    def __init__(self, max_size: int = 2000, default_ttl: float = 3600.0) -> None:
        super().__init__(max_size=max_size, default_ttl=default_ttl)

    @staticmethod
    def make_key(text: str, model: str = "") -> str:
        """生成缓存 key。"""
        return f"{model}:{text.strip().lower()}"


# ── 后台清理协程 ─────────────────────────────────────────

async def start_cache_cleanup_worker(
    interval: float = 300.0,
    query_cache: Optional[QueryCache] = None,
    embedding_cache: Optional[EmbeddingCache] = None,
) -> None:
    """在后台定期清理过期缓存。

    通过 lifespan 中的 asyncio.create_task 启动。
    """
    import asyncio

    while True:
        await asyncio.sleep(interval)
        if query_cache:
            query_cache.cleanup()
        if embedding_cache:
            embedding_cache.cleanup()


# ── 全局单例 ─────────────────────────────────────────────

query_cache = QueryCache()
embedding_cache = EmbeddingCache()


__all__ = [
    "TTLCache",
    "QueryCache",
    "EmbeddingCache",
    "query_cache",
    "embedding_cache",
    "start_cache_cleanup_worker",
]
