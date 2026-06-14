"""Splitter 实现包 -- 导入即触发工厂注册。"""

from app.libs.splitter.langchain_impl import (
    HTMLHeaderSplitter,
    MarkdownHeaderSplitter,
    RecursiveCharacterSplitter,
)
from app.libs.factory import SplitterFactory

# ── 注册默认实现 ────────────────────────────────────────────

SplitterFactory.register("markdown_header", MarkdownHeaderSplitter)
SplitterFactory.register("html_header", HTMLHeaderSplitter)
SplitterFactory.register("recursive_character", RecursiveCharacterSplitter)

__all__ = ["MarkdownHeaderSplitter", "HTMLHeaderSplitter", "RecursiveCharacterSplitter"]
