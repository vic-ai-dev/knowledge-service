"""PDF Loader — 使用 MarkItDown 将 PDF 转换为 Markdown 文本。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from markitdown import MarkItDown

from app.factory.base.base_loader import BaseLoader, LoadResult
from app.common.log import get_logger

logger = get_logger(__name__)


class PDFLoader(BaseLoader):
    """PDF 文档加载器。

    使用 MarkItDown 将 PDF 转换为 Markdown 格式文本，保留标题结构与元数据。
    """

    async def load(self, path: str | Path, **kwargs) -> list[LoadResult]:
        """加载 PDF 文件并转换为 Markdown 文本。"""
        path_str = str(path)
        loop = asyncio.get_running_loop()

        try:
            result = await loop.run_in_executor(None, self._convert, path_str)
        except Exception as e:
            logger.error(
                "pdf_load_failed",
                metadata={"source_path": path_str},
                error=str(e),
            )
            raise

        metadata = {
            "source_path": path_str,
            "title": result.title or "",
        }

        logger.info(
            "pdf_load_complete",
            metadata={
                "source_path": path_str,
                "title": result.title,
                "length": len(result.markdown),
            },
        )

        return [
            LoadResult(
                text=result.markdown,
                metadata=metadata,
                source_path=path_str,
            )
        ]

    @staticmethod
    def _convert(path: str) -> "DocumentConverterResult":
        """同步 PDF → Markdown 转换（在线程池中执行）。"""
        from markitdown._base_converter import DocumentConverterResult

        md = MarkItDown()
        return md.convert(path)


__all__ = ["PDFLoader"]
