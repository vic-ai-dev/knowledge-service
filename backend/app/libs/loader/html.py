"""HTML Loader — 直接读取 HTML 文件内容。"""

from __future__ import annotations

from pathlib import Path

from app.libs.base.base_loader import BaseLoader, LoadResult
from app.common.log import get_logger

logger = get_logger(__name__)


class HTMLLoader(BaseLoader):
    """HTML 文档加载器。

    直接读取 .html 文件内容，保留原始 HTML 格式供 HTMLSplitter 处理。
    """

    async def load(self, path: str | Path, **kwargs) -> list[LoadResult]:
        """加载 HTML 文件。"""
        path_str = str(path)

        import aiofiles

        try:
            async with aiofiles.open(path_str, encoding="utf-8") as f:
                content = await f.read()
        except Exception as e:
            logger.error(
                "html_load_failed",
                metadata={"source_path": path_str},
                error=str(e),
            )
            raise

        metadata = {
            "source_path": path_str,
        }

        logger.info(
            "html_load_complete",
            metadata={
                "source_path": path_str,
                "length": len(content),
            },
        )

        return [
            LoadResult(
                text=content,
                metadata=metadata,
                source_path=path_str,
            )
        ]


__all__ = ["HTMLLoader"]
