"""C15 — CLI 入口：从命令行触发文件摄取。

用法:
    uv run python -m app.ingestion.ingest <file_or_directory> \\
        --category <category> --language <lang> \\
        [--collection <name>] [--title <title>] [--force]

示例:
    uv run python -m app.ingestion.ingest ~/docs/sample.pdf \\
        --category technical_spec --language zh

    uv run python -m app.ingestion.ingest ~/docs/ \\
        --category employee_handbook --language en

支持的 category 值:
    employee_handbook, compliance, technical_spec, architecture

支持的 language 值:
    zh, en
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.ingestion.models import IngestionDocument
from app.ingestion.pipeline import IngestionPipeline
from app.common.log import get_logger
from app.common.enums import Category, Language, DocType, IngestionStatus, CATEGORY_VALUES, LANGUAGE_VALUES, DOCTYPE_VALUES

logger = get_logger("ingest.cli")


_SUPPORTED_EXTENSIONS = {".pdf", ".md", ".html", ".htm"}
_SUPPORTED_CATEGORIES = CATEGORY_VALUES
_SUPPORTED_LANGUAGES = LANGUAGE_VALUES


def _resolve_files(path: str) -> list[Path]:
    """解析文件或目录，返回支持的文件列表。"""
    p = Path(path).expanduser().resolve()

    if not p.exists():
        print(f"Error: path does not exist: {p}", file=sys.stderr)
        sys.exit(1)

    if p.is_file():
        if p.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            print(
                f"Error: unsupported file type: {p.suffix} "
                f"(supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))})",
                file=sys.stderr,
            )
            sys.exit(1)
        return [p]

    # 目录 → 递归扫描
    files: list[Path] = []
    for ext in _SUPPORTED_EXTENSIONS:
        files.extend(p.rglob(f"*{ext}"))
    files.extend(p.rglob("*.htm"))  # .htm 也需要

    if not files:
        print(
            f"Warning: no supported files found in {p}",
            file=sys.stderr,
        )
        sys.exit(0)

    return sorted(files)


def _infer_category(path: Path) -> str:
    """从路径和文件名推断 category（默认 technical_spec）。"""
    p_lower = str(path).lower()
    for cat in _SUPPORTED_CATEGORIES:
        if cat in p_lower:
            return cat
    return Category.TECHNICAL_SPEC.value


def _infer_language(path: Path) -> str:
    """从路径和文件名推断语言（默认 zh）。"""
    p_lower = str(path).lower()
    for lang in _SUPPORTED_LANGUAGES:
        if lang in p_lower or (lang == Language.EN.value and "english" in p_lower):
            return lang
    return Language.ZH.value


def _infer_doc_type(path: Path) -> str:
    """根据文件后缀推断 doc_type。"""
    suffix = path.suffix.lower()
    if suffix == ".md":
        return DocType.MD.value
    elif suffix in (".html", ".htm"):
        return DocType.HTML.value
    else:
        return DocType.PDF.value


async def _run(args: argparse.Namespace) -> None:
    files = _resolve_files(args.path)

    documents: list[IngestionDocument] = []
    for f in files:
        doc = IngestionDocument(
            source_path=str(f),
            doc_type=_infer_doc_type(f),
            category=args.category or _infer_category(f),
            language=args.language or _infer_language(f),
            title=args.title or f.stem,
        )
        documents.append(doc)

    print(f"Found {len(documents)} file(s) to process")

    pipeline = IngestionPipeline()

    try:
        results = await pipeline.process_batch(documents)

        ok = sum(1 for r in results if r.status.value == IngestionStatus.COMPLETED.value)
        skipped = sum(1 for r in results if r.status.value == IngestionStatus.SKIPPED.value)
        failed = sum(1 for r in results if r.status.value == IngestionStatus.FAILED.value)

        print(f"\n{'=' * 60}")
        print(f"Results:  {ok} completed, {skipped} skipped, {failed} failed")
        print(f"{'=' * 60}")

        for r in results:
            if r.status.value == IngestionStatus.FAILED.value:
                print(
                    f"  [FAIL] {r.source_path}: {'; '.join(r.errors)}"
                )
            elif r.status.value == IngestionStatus.SKIPPED.value:
                print(f"  [SKIP] {r.source_path}")
            else:
                print(
                    f"  [OK]   {r.source_path} → "
                    f"{r.total_chunks} chunks"
                )

    finally:
        await pipeline.close()


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="Knowledge Service — 文件摄取工具",
    )
    parser.add_argument(
        "path",
        help="文件或目录路径",
    )
    parser.add_argument(
        "--category",
        choices=sorted(_SUPPORTED_CATEGORIES),
        help=f"知识分类（默认自动推断）",
    )
    parser.add_argument(
        "--language",
        choices=sorted(_SUPPORTED_LANGUAGES),
        help=f"语言（默认自动推断）",
    )
    parser.add_argument(
        default="default",
    )
    parser.add_argument(
        "--title",
        help="文档标题（默认文件名）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新处理（跳过完整性检查）",
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()


__all__ = ["main"]
