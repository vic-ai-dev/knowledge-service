"""D1 — QueryProcessor：查询请求处理与验证。

将用户原始查询文本转换为内部 ``RetrievalQuery`` 对象，
支持关键词提取、过滤条件解析、查询模式验证。
"""

from __future__ import annotations

from typing import Any

from app.core.query_engine.query_types import RetrievalQuery
from app.common.log import get_logger

logger = get_logger(__name__)


class QueryProcessorError(RuntimeError):
    """QueryProcessor 通用异常。"""
    pass


class QueryProcessor:
    """查询请求处理器。

    职责：
      1. 验证输入参数合法
      2. 构建 ``RetrievalQuery`` 内部查询对象
      3. 参数零值处理与默认值填充
    """

    VALID_SEARCH_MODES = ("vector_only", "hybrid")

    # ── 输入校验 ──────────────────────────────────────────────

    def _validate_query_text(self, query_text: str) -> None:
        if not query_text or not query_text.strip():
            raise QueryProcessorError("query_text cannot be empty")

    def _validate_search_mode(self, search_mode: str) -> None:
        if search_mode not in self.VALID_SEARCH_MODES:
            raise QueryProcessorError(
                f"invalid search_mode '{search_mode}'. "
                f"Must be one of: {self.VALID_SEARCH_MODES}"
            )

    def _validate_top_k(self, top_k: int) -> None:
        if top_k < 1:
            raise QueryProcessorError(f"top_k must be >= 1, got {top_k}")
        if top_k > 100:
            raise QueryProcessorError(
                f"top_k too large ({top_k}), max is 100"
            )

    def _validate_rerank(self, rerank: bool) -> None:
        if not isinstance(rerank, bool):
            raise QueryProcessorError(
                f"rerank must be boolean, got {type(rerank)}"
            )

    # ── 核心方法 ──────────────────────────────────────────────

    def process(
        self,
        query_text: str,
        search_mode: str = "hybrid",
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        rerank: bool = True,
    ) -> RetrievalQuery:
        """验证并转换原始查询为内部查询对象。

        Args:
            query_text: 用户原始查询文本。
            search_mode: 检索模式，``hybrid`` 或 ``vector_only``。
            top_k: 返回的最大结果数。
            filters: 附加过滤条件（category / language / doc_type 等）。
            rerank: 是否启用重排序。

        Returns:
            构建好的 RetrievalQuery 对象。

        Raises:
            QueryProcessorError: 任何验证失败。
        """
        # 校验
        self._validate_query_text(query_text)
        self._validate_search_mode(search_mode)
        self._validate_top_k(top_k)
        self._validate_rerank(rerank)

        # 构建查询对象
        query = RetrievalQuery(
            query_text=query_text.strip(),
            search_mode=search_mode,
            top_k=top_k,
            filters=filters or None,  # 空 dict 转 None
            rerank=rerank,
        )

        logger.info(
            "query_processed",
            metadata={
                "search_mode": query.search_mode,
                "top_k": query.top_k,
                "rerank": query.rerank,
                "has_filters": query.filters is not None,
            },
        )

        return query


__all__ = ["QueryProcessor", "QueryProcessorError"]
