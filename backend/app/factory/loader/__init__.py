"""Loader 实现注册。

导入所有 Loader 实现并在 LoaderFactory 中注册，支持按 doc_type 路由。
"""

from __future__ import annotations

from app.factory.factory import LoaderFactory
from app.factory.loader.html import HTMLLoader
from app.factory.loader.markdown import MarkdownLoader
from app.factory.loader.pdf import PDFLoader

# ── 注册到工厂 ─────────────────────────────────────────
LoaderFactory.register("pdf", PDFLoader)
LoaderFactory.register("md", MarkdownLoader)
LoaderFactory.register("html", HTMLLoader)

__all__ = [
    "PDFLoader",
    "MarkdownLoader",
    "HTMLLoader",
]
