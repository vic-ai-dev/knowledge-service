"""Loader 实现注册。

导入所有 Loader 实现并在 LoaderFactory 中注册，支持按 doc_type 路由。
"""

from __future__ import annotations

from app.libs.factory import LoaderFactory
from app.libs.loader.html import HTMLLoader
from app.libs.loader.markdown import MarkdownLoader
from app.libs.loader.pdf import PDFLoader

# ── 注册到工厂 ─────────────────────────────────────────
LoaderFactory.register("pdf", PDFLoader)
LoaderFactory.register("md", MarkdownLoader)
LoaderFactory.register("html", HTMLLoader)

__all__ = [
    "PDFLoader",
    "MarkdownLoader",
    "HTMLLoader",
]
