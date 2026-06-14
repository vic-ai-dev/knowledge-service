"""D7 — CLI 入口：从命令行执行检索查询。

用法:
    uv run python -m app.ingestion.query "你的查询文本" \\
        --mode hybrid --top-k 10 --rerank

示例:
    uv run python -m app.ingestion.query "公司的年假政策是什么" \\
        --mode hybrid --top-k 5 --rerank

    uv run python -m app.ingestion.query "vacation policy" \\
        --mode vector_only --no-rerank

支持的 search_mode 值:
    hybrid, vector_only
"""

from __future__ import annotations

import argparse
import asyncio
import time

from app.core.query_engine.hybrid_search import HybridSearch, HybridSearchError
from app.core.query_engine.query_processor import QueryProcessor, QueryProcessorError


def _format_results(results: list, elapsed_ms: float) -> None:
    """格式化打印检索结果。"""
    print(f"\n{'=' * 70}")
    print(f"  Found {len(results)} result(s) in {elapsed_ms:.0f}ms")
    print(f"{'=' * 70}")

    for i, r in enumerate(results, start=1):
        print(f"\n  [{i}] Score: {r.score:.4f}")
        if r.source_path:
            print(f"      Source: {r.source_path}")
        if r.chunk_id:
            print(f"      Chunk: {r.chunk_id[:20]}...")
        text_preview = r.text[:200].replace("\n", " ")
        print(f"      Text: {text_preview}...")
        print(f"      {'─' * 66}")


async def _run(args: argparse.Namespace) -> None:
    try:
        processor = QueryProcessor()
        query = processor.process(
            query_text=args.query,
            search_mode=args.mode,
            top_k=args.top_k,
            rerank=args.rerank,
        )

        print(f"\n  Query: {query.query_text}")
        print(f"  Mode:  {query.search_mode}")
        print(f"  Top-K: {query.top_k}")
        print(f"  Rerank: {query.rerank}")

        hybrid_search = HybridSearch()
        t0 = time.monotonic()
        result = await hybrid_search.search(query)
        elapsed = (time.monotonic() - t0) * 1000

        _format_results(result.results, elapsed)

    except (QueryProcessorError, HybridSearchError) as e:
        print(f"\n  Error: {e}")


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="Knowledge Service — 检索查询工具",
    )
    parser.add_argument(
        "query",
        help="查询文本",
    )
    parser.add_argument(
        "--mode",
        choices=["hybrid", "vector_only"],
        default="hybrid",
        help="检索模式（默认 hybrid）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="返回的最大结果数（默认 10）",
    )
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="启用/禁用重排序（默认启用）",
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()


__all__ = ["main"]
