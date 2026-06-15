"""Langchain 分块实现。

包装 langchain_text_splitters 的标准分块策略，遵循 BaseSplitter 契约。
"""

from __future__ import annotations

from typing import Any

from langchain_text_splitters import (
    HTMLHeaderTextSplitter as _HTMLHeaderTextSplitter,
    MarkdownHeaderTextSplitter as _MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter as _RecursiveCharacterTextSplitter,
)
from langchain_core.documents import Document

from app.libs.base.base_splitter import BaseSplitter, SplitResult
from app.common.log import get_logger

logger = get_logger(__name__)


class SplitterValidationError(ValueError):
    """Splitter 输入校验异常。"""
    pass


class MarkdownHeaderSplitter(BaseSplitter):
    """Markdown 标题分块实现。
    
    按 Markdown 标题层级（# / ## / ###）切分文档，保留标题上下文。
    """

    def __init__(self, **kwargs: Any):
        headers_to_split_on = kwargs.pop(
            "headers_to_split_on",
            [["#", "h1"], ["##", "h2"], ["###", "h3"]],
        )
        self._chunk_size = kwargs.get("chunk_size", 1000)
        self._chunk_overlap = kwargs.get("chunk_overlap", 200)
        self._splitter = _MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
        )

    def _validate_text(self, text: str) -> None:
        if not text or not text.strip():
            raise SplitterValidationError("text cannot be empty")

    def split(self, text: str, metadata: dict | None = None) -> list[SplitResult]:
        self._validate_text(text)
        import time
        start = time.monotonic()
        docs: list[Document] = self._splitter.split_text(text)
        result = [
            SplitResult(
                text=doc.page_content,
                metadata={**doc.metadata, **(metadata or {})},
                chunk_index=i,
            )
            for i, doc in enumerate(docs)
        ]
        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.info("split_done", metadata={
            "splitter": "MarkdownHeaderSplitter",
            "chunks": len(result),
            "duration_ms": elapsed,
        })
        return result

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap


class HTMLHeaderSplitter(BaseSplitter):
    """HTML 标题分块实现。
    
    按 HTML 标题标签（h1 / h2 / h3）切分文档，保留标题上下文。
    """

    def __init__(self, **kwargs: Any):
        headers_to_split_on = kwargs.pop(
            "headers_to_split_on",
            [["h1", "h1"], ["h2", "h2"], ["h3", "h3"]],
        )
        self._chunk_size = kwargs.get("chunk_size", 1000)
        self._chunk_overlap = kwargs.get("chunk_overlap", 200)
        self._splitter = _HTMLHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
        )

    def _validate_text(self, text: str) -> None:
        if not text or not text.strip():
            raise SplitterValidationError("text cannot be empty")

    def split(self, text: str, metadata: dict | None = None) -> list[SplitResult]:
        self._validate_text(text)
        import time
        start = time.monotonic()
        docs: list[Document] = self._splitter.split_text(text)
        result = [
            SplitResult(
                text=doc.page_content,
                metadata={**doc.metadata, **(metadata or {})},
                chunk_index=i,
            )
            for i, doc in enumerate(docs)
        ]
        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.info("split_done", metadata={
            "splitter": "HTMLHeaderSplitter",
            "chunks": len(result),
            "duration_ms": elapsed,
        })
        return result

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap


class RecursiveCharacterSplitter(BaseSplitter):
    """递归字符分块实现。
    
    按分隔符优先级（段落 → 句号 → 逗号 → 空格 → 字符）递归切分，
    确保尽量在语义边界断句。
    """

    def __init__(self, **kwargs: Any):
        self._chunk_size = kwargs.get("chunk_size", 1000)
        self._chunk_overlap = kwargs.get("chunk_overlap", 200)
        separators = kwargs.get("separators")
        self._splitter = _RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=separators,
        )

    def _validate_text(self, text: str) -> None:
        if not text or not text.strip():
            raise SplitterValidationError("text cannot be empty")

    def split(self, text: str, metadata: dict | None = None) -> list[SplitResult]:
        self._validate_text(text)
        import time
        start = time.monotonic()
        docs: list[Document] = self._splitter.split_text(text)
        result = [
            SplitResult(
                text=doc.page_content if isinstance(doc, Document) else doc,
                metadata=dict(metadata or {}),
                chunk_index=i,
            )
            for i, doc in enumerate(docs)
        ]
        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.info("split_done", metadata={
            "splitter": "RecursiveCharacterSplitter",
            "chunks": len(result),
            "duration_ms": elapsed,
        })
        return result

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap
