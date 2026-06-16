"""一键评估脚本 (One-Click Evaluation Script).

基于 golden test dataset / query_traces，通过 ragas 库评估 RAG 管线质量。
设计要点：
- 优先走 query_traces 缓存（避免重复调 LLM），--force 可强制重新跑
- 按文件批次提交 ragas，而非逐条（ragets 内部可并行深度求值）
- Ollama embedding 不兼容 ragas，会降级跳过需要 embedding 的指标

Usage:

  uv run python scripts/eval_oneclick.py
  uv run python scripts/eval_oneclick.py --mode golden --lang zh
  uv run python scripts/eval_oneclick.py --mode traces --recent 50
  uv run python scripts/eval_oneclick.py --force
  uv run python scripts/eval_oneclick.py --dataset 架构文档
  uv run python scripts/eval_oneclick.py --dataset Golden_Test_Set_Architecture_en

Mode A (golden) workflow:
  1. Scan golden_test_dataset/*.json, parse question/ground_truths
  2. For each query:
     2.1 query_traces has match -> use cached top_k_results / results
     2.2 no match -> call query engine (retrieval + LLM)
  3. Submit batch to ragas per file
  4. Write individual results to evaluation_results
  5. Print summary
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import structlog
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

# ── ragas 批量评估 ──
from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import aevaluate
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.common.log import get_logger
from app.common.settings import get_settings

logger = get_logger(__name__)

# Paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GOLDEN_DIR = _PROJECT_ROOT / "golden_test_dataset"

# Database connection
# 直连知识库（knowledge）数据库，不含 knowledge_rag（向量/B25 由管线内部处理）
_DB_DSN = "postgresql+asyncpg://postgres:root123456@localhost:5432/knowledge"


# ====================================================================
# Data loading
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════════════

def _load_golden_files(lang: str | None = None, dataset: str | None = None) -> list[dict[str, Any]]:
    """从 golden_test_dataset/*.json 加载测试集。

    每个 JSON 文件格式：
      {"question": ["Q1", "Q2", ...],
       "ground_truths": [["A1"], ["A2"], ...]}

    文件名 → (category, language) 映射见 _FILE_META。
    lang / dataset 参数用于筛选。
    """
    if not _GOLDEN_DIR.is_dir():
        logger.error("golden_test_dataset directory not found at %s", _GOLDEN_DIR)
        sys.exit(1)

    _FILE_META: dict[str, tuple[str, str]] = {
        "黄金测试集_员工手册_zh":       ("employee_handbook", "zh"),
        "黄金测试集_合规指南_zh":       ("compliance", "zh"),
        "黄金测试集_技术规范_zh":       ("technical_spec", "zh"),
        "黄金测试集_架构文档_zh":       ("architecture", "zh"),
        "黄金测试集_业务文档_zh":       ("business_documents", "zh"),
        "Golden_Test_Set_Employee_Handbook_en":  ("employee_handbook", "en"),
        "Golden_Test_Set_Compliance_en":         ("compliance", "en"),
        "Golden_Test_Set_Technical_Standards_en":("technical_spec", "en"),
        "Golden_Test_Set_Architecture_en":       ("architecture", "en"),
        "Golden_Test_Set_Business_Documents_en": ("business_documents", "en"),
    }

    entries: list[dict[str, Any]] = []
    for fpath in sorted(_GOLDEN_DIR.glob("*.json")):
        stem = fpath.stem
        meta = _FILE_META.get(stem)
        if meta is None:
            logger.warning("Skipping unknown golden file: %s", stem)
            continue
        category, language = meta
        if lang and language != lang:
            continue
        if dataset and dataset not in stem:
            continue

        with open(fpath, encoding="utf-8") as f:
            raw = json.load(f)

        questions = raw.get("question", [])
        ground_truths_list = raw.get("ground_truths", [])
        n = len(questions)
        queries = []
        for i in range(n):
            queries.append({
                "query": questions[i],
                "ground_truth": (
                    ground_truths_list[i]
                    if i < len(ground_truths_list) and ground_truths_list[i]
                    else []
                ),
            })

        entries.append({
            "name": stem,
            "category": category,
            "language": language,
            "file_path": str(fpath),
            "queries": queries,
            "query_count": len(queries),
        })
        logger.info(
            "golden_file_loaded",
            metadata={
                "file": stem,
                "category": category,
                "language": language,
                "queries": len(queries),
            },
        )
    return entries


async def _load_query_traces(
    session: AsyncSession, recent: int = 100
) -> list[dict[str, Any]]:
    """从 query_traces 表拉取最近 N 条用户查询（去重）。

    Mode B (traces) 专用，不包含 ground_truth，
    因此评估时 context_precision / context_recall 会跳过。
    """
    from app.model.entity.query import QueryTrace

    stmt = (
        select(QueryTrace)
        .order_by(QueryTrace.created_at.desc())
        .limit(recent)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        logger.warning("query_traces table is empty, nothing to evaluate")
        return []

    # user_query 去重，相同问题只保留最近一次
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for row in rows:
        q = row.user_query.strip()
        if not q or q in seen:
            continue
        seen.add(q)
        entries.append({
            "query": q,
            "ground_truth": [],
            "category": row.category or "",
            "language": row.language or "",
        })

    logger.info(
        "query_traces_loaded",
        metadata={"total": len(rows), "unique": len(entries)},
    )
    return [
        {
            "name": f"query_traces_top{recent}",
            "category": "mixed",
            "language": "mixed",
            "file_path": "",
            "queries": entries,
            "query_count": len(entries),
        }
    ]


# ====================================================================
# Ragas helpers
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# ragas LLM / Embedding 工厂
# ═══════════════════════════════════════════════════════════════════

def _build_ragas_llm() -> LangchainLLMWrapper:
    """构造 ragas 可用的 LLM 包装器（复用 settings.yaml 的 LLM 配置）。"""
    cfg = get_settings().llm
    api_key = (
        cfg.api_key.get_secret_value()
        if hasattr(cfg.api_key, "get_secret_value")
        else cfg.api_key
    )
    chat = ChatOpenAI(
        model=cfg.model,
        api_key=api_key,
        base_url=cfg.base_url,
        temperature=getattr(cfg, "temperature", 0.0),
        max_tokens=getattr(cfg, "max_tokens", 4096),
    )
    return LangchainLLMWrapper(chat)


def _build_ragas_embeddings():
    """构造 ragas 可用的 Embedding 包装器。

    注意: ragas 0.4.3 的 LangchainEmbeddingsWrapper 仅兼容 OpenAI 格式。
    Ollama 场景返回 None，会跳过需要 embedding 的指标（answer_relevancy / context_recall）。
    等 ragas 升级或接入自定义 Wrapper 后恢复。
    """
    cfg = get_settings().embedding
    if cfg.provider == "ollama":
        return None
    try:
        from langchain_openai import OpenAIEmbeddings
        from ragas.embeddings.base import LangchainEmbeddingsWrapper

        if not cfg.api_key:
            return None
        client = OpenAIEmbeddings(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )
        return LangchainEmbeddingsWrapper(client)
    except Exception:
        return None


# ====================================================================
# QueryTrace cache lookup
# ====================================================================

async def _find_trace(session: AsyncSession, query_text: str):
    """Look up query_traces for the latest matching trace (exact match)."""
    from app.model.entity.query import QueryTrace

    stmt = (
        select(QueryTrace)
        .where(QueryTrace.user_query == query_text)
        .order_by(QueryTrace.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ====================================================================
# Resolve a single query: answer + contexts
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# 单条 query 的 answer + contexts 解析
# 优先读取 query_traces 缓存，未命中则调 pipeline
# ═══════════════════════════════════════════════════════════════════

async def _resolve_query(
    session: AsyncSession,
    query_text: str,
    ground_truth: list[str],
    search_mode: str,
    top_k: int,
    rerank: bool,
    force: bool,
    pipeline: Any,
) -> tuple[str, list[str], Any]:
    """Get answer and contexts for one query.

    Returns (answer, contexts, pipeline) — pipeline is reused across calls.
    """
    if not force:
        trace = await _find_trace(session, query_text)
    else:
        trace = None

    if trace:
        # top_k_results is stored as TEXT; asyncpg may auto-deserialize to list
        raw = trace.top_k_results
        if isinstance(raw, str):
            top_k_raw = json.loads(raw) if raw else []
        else:
            top_k_raw = raw or []
        contexts = [item["text"] for item in top_k_raw]
        answer = trace.results or ""
        logger.info(
            "eval_cache_hit",
            metadata={"query": query_text[:60], "contexts": len(contexts)},
        )
        return answer, contexts, pipeline

    # Cache miss: run query engine
    from app.query_engine.pipeline import QueryPipeline

    if pipeline is None:
        pipeline = QueryPipeline()
    result = await pipeline.execute(
        query_text=query_text,
        search_mode=search_mode,
        top_k=top_k,
        rerank=rerank,
        kb_session=session,  # auto-saves QueryTrace
    )
    contexts = [r.text for r in result.results]
    answer = result.answer or ""
    logger.info(
        "eval_cache_miss",
        metadata={"query": query_text[:60], "contexts": len(contexts)},
    )
    return answer, contexts, pipeline


# ====================================================================
# Batch evaluation for one file
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# 按文件批次执行评估（核心函数）
# ═══════════════════════════════════════════════════════════════════

async def _eval_file_batch(
    session: AsyncSession,
    entry: dict[str, Any],
    search_mode: str,
    top_k: int,
    rerank: bool,
    force: bool,
) -> dict[str, Any]:
    """Evaluate one golden file using batch ragas."""
    name = entry["name"]
    queries = entry["queries"]
    category = entry["category"]
    language = entry["language"]

    llm = _build_ragas_llm()
    embeddings = _build_ragas_embeddings()

    # Step 1: resolve each query
    batch_q: list[str] = []
    batch_a: list[str] = []
    batch_c: list[list[str]] = []
    batch_gt: list[list[str]] = []

    pipeline: Any = None
    t_start = time.monotonic()
    failed_count = 0

    for q in queries:
        query_text = q["query"]
        ground_truth = q["ground_truth"]
        try:
            answer, contexts, pipeline = await _resolve_query(
                session=session,
                query_text=query_text,
                ground_truth=ground_truth,
                search_mode=search_mode,
                top_k=top_k,
                rerank=rerank,
                force=force,
                pipeline=pipeline,
            )
            batch_q.append(query_text)
            batch_a.append(answer)
            batch_c.append(contexts)
            batch_gt.append(ground_truth)
        except Exception as e:
            logger.error(
                "eval_query_failed",
                error=str(e),
                metadata={"query": query_text[:60]},
            )
            failed_count += 1

    # 全部失败，无有效数据可评估，直接返回空结果
    if not batch_q:
        await session.commit()
        return {
            "name": name,
            "category": category,
            "language": language,
            "query_count": 0,
            "passed": 0,
            "failed": failed_count,
            "elapsed_s": round(time.monotonic() - t_start, 2),
            "avg_hit_rate": 0,
            "avg_mrr": 0,
            "avg_ndcg": 0,
            "avg_faithfulness": 0,
            "avg_answer_relevancy": 0,
            "avg_context_precision": 0,
        }

    # Step 2: build ragas Dataset
    has_gt = any(len(gt) > 0 and bool(gt[0]) for gt in batch_gt)
    dataset_dict: dict[str, Any] = {
        "question": batch_q,
        "answer": batch_a,
        "contexts": batch_c,
    }
    if has_gt:
        dataset_dict["reference"] = [
            gt[0] if gt and len(gt) > 0 else "" for gt in batch_gt
        ]

    dataset = Dataset.from_dict(dataset_dict)

    # Step 3: 筛选可用指标
    # faithfulness: 始终可用（仅需 LLM）
    # answer_relevancy: 需要 embedding（Ollama 场景跳过）
    # context_precision: 需要 ground_truth
    # context_recall: 需要 ground_truth + embedding
    metrics = [faithfulness]
    if embeddings is not None:
        metrics.append(answer_relevancy)
    if has_gt:
        metrics.append(context_precision)
        if embeddings is not None:
            metrics.append(context_recall)

    logger.info(
        "ragas_batch_start",
        metadata={
            "name": name,
            "batch_size": len(batch_q),
            "metrics": [m.name for m in metrics],
            "has_gt": has_gt,
            "has_emb": embeddings is not None,
        },
    )

    # Step 4: batch ragas
    try:
        ragas_result = await aevaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
            raise_exceptions=True,
        )
    except Exception as e:
        logger.error("ragas_batch_failed", error=str(e), metadata={"name": name})
        from app.model.entity.evaluation import EvaluationResult

        # 整批失败，将错误信息写入所有 evaluation_result 行
        for q_text in batch_q:
            session.add(EvaluationResult(metrics={"error": str(e)}, test_set=name))
        await session.commit()
        return {
            "name": name,
            "category": category,
            "language": language,
            "query_count": len(batch_q),
            "passed": 0,
            "failed": len(batch_q) + failed_count,
            "elapsed_s": round(time.monotonic() - t_start, 2),
            "avg_hit_rate": 0,
            "avg_mrr": 0,
            "avg_ndcg": 0,
            "avg_faithfulness": 0,
            "avg_answer_relevancy": 0,
            "avg_context_precision": 0,
        }

    # Step 5: 写入 evaluation_results 表（逐条）
    from app.model.entity.evaluation import EvaluationResult

    n = len(batch_q)
    all_rows: list[dict[str, float | None]] = []
    passed = 0

    for i in range(n):
        row: dict[str, float | None] = {}
        for m in metrics:
            col = m.name
            try:
                # ragas 0.4.3 EvaluationResult.__getitem__ returns list of floats
                all_scores = ragas_result[col]
                row[col] = float(all_scores[i])
            except (KeyError, TypeError, ValueError, IndexError):
                row[col] = None

        cleaned = {k: v for k, v in row.items() if v is not None}
        session.add(EvaluationResult(metrics=cleaned, test_set=name))
        all_rows.append(row)
        if any(v is not None for v in row.values()):
            passed += 1

    await session.commit()
    elapsed = round(time.monotonic() - t_start, 2)

    # 汇总均值
    def _avg(key: str) -> float:
        vals = [r[key] for r in all_rows if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {
        "avg_hit_rate": 0.0,
        "avg_mrr": 0.0,
        "avg_ndcg": 0.0,
        "avg_faithfulness": _avg("faithfulness"),
        "avg_answer_relevancy": _avg("answer_relevancy"),
        "avg_context_precision": _avg("context_precision"),
    }

    logger.info(
        "eval_file_done",
        metadata={
            "name": name,
            "passed": passed,
            "failed": n - passed,
            "elapsed_s": elapsed,
            **summary,
        },
    )

    return {
        "name": name,
        "category": category,
        "language": language,
        "query_count": n,
        "passed": passed,
        "failed": (n - passed) + failed_count,
        "elapsed_s": elapsed,
        **summary,
    }


# ====================================================================
# Output helpers
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# 终端输出
# ═══════════════════════════════════════════════════════════════════

def _print_summary(results: list[dict]) -> None:
    print()
    print("=" * 60)
    print("  ONE-CLICK EVALUATION  SUMMARY")
    print("=" * 60)

    n_files = len(results)
    total_q = sum(r["query_count"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_elapsed = round(sum(r["elapsed_s"] for r in results), 2)

    summary = {
        "total_files": n_files,
        "total_queries": total_q,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_elapsed_s": total_elapsed,
        "files": [],
    }
    for r in results:
        summary["files"].append({
            "name": r["name"],
            "category": r["category"],
            "language": r["language"],
            "query_count": r["query_count"],
            "passed": r["passed"],
            "failed": r["failed"],
            "faithfulness": r.get("avg_faithfulness", 0),
            "answer_relevancy": r.get("avg_answer_relevancy", 0),
            "context_precision": r.get("avg_context_precision", 0),
            "elapsed_s": r["elapsed_s"],
        })

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()


# ====================================================================
# Main
# ====================================================================

# ═══════════════════════════════════════════════════════════════════
# 日志 / 文件输出工具 —— Tee stdout → log file
# ═══════════════════════════════════════════════════════════════════

class _Tee:
    """Tee a stream: write to both the original stream and a log file."""
    def __init__(self, original: TextIO, fileobj: TextIO) -> None:
        self.original = original
        self.fileobj = fileobj

    def write(self, text: str) -> None:
        self.original.write(text)
        self.fileobj.write(text)
        self.fileobj.flush()

    def flush(self) -> None:
        self.original.flush()
        self.fileobj.flush()


def _setup_eval_log(entry_name: str) -> tuple[Path, TextIO]:
    """Tee sys.stdout to both console and a log file under backend/eval_log/."""
    log_dir = _PROJECT_ROOT / "backend" / "eval_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', "_", entry_name).strip("_")
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    log_path = log_dir / f"{safe_name}_{timestamp}.log"
    log_file = open(str(log_path), "w", encoding="utf-8")  # noqa: SIM115
    sys.stdout = _Tee(sys.stdout, log_file)
    return log_path, log_file

async def main() -> None:
    parser = argparse.ArgumentParser(description="One-Click Evaluation Script")
    parser.add_argument(
        "--mode",
        choices=["golden", "traces"],
        default="golden",
        help="Evaluation mode",
    )
    parser.add_argument("--lang", choices=["zh", "en"], default=None)
    parser.add_argument("--dataset", type=str, default=None,
                        help="Filter: only run golden files whose name contains this substring")
    parser.add_argument("--recent", type=int, default=100)
    parser.add_argument(
        "--search-mode",
        choices=["hybrid", "vector_only"],
        default="hybrid",
    )
    parser.add_argument("--rerank", action="store_true", default=True)
    parser.add_argument("--no-rerank", action="store_false", dest="rerank")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-run pipeline (skip query_traces cache)",
    )
    args = parser.parse_args()

    # 连接知识库 DB，确保 evaluation_results 表存在
    engine = create_async_engine(_DB_DSN)
    async with engine.begin() as conn:
        from app.model.entity.base import KnowledgeBase

        await conn.run_sync(KnowledgeBase.metadata.create_all)
    # 使用 session_factory 创建每个文件所需的独立 session
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # ── Mode A: golden test set ──
        if args.mode == "golden":
            entries = _load_golden_files(lang=args.lang, dataset=args.dataset)
            if not entries:
                print("No golden test files found.")
                await engine.dispose()
                return

            print(
                f"\n  Loaded {len(entries)} golden test files "
                f"({sum(e['query_count'] for e in entries)} queries total)"
            )

            # 逐文件执行 batch 评估
            # Add eval log file handler
            log_path, log_handler = _setup_eval_log(entries[0]["name"] if entries else "eval")
            results: list[dict] = []
            try:
                for entry in entries:
                    r = await _eval_file_batch(
                        session=session,
                        entry=entry,
                        search_mode=args.search_mode,
                        top_k=args.top_k,
                        rerank=args.rerank,
                        force=args.force,
                    )
                    results.append(r)
            finally:
                sys.stdout.flush()
                log_handler.close()
                sys.stdout = sys.__stdout__
                print(f"\n  Log saved to: {log_path}")

        else:
            entries = await _load_query_traces(session, recent=args.recent)
            if not entries:
                print("No query_traces data found.")
                await engine.dispose()
                return

            print(
                f"\n  Loaded {entries[0]['query_count']} unique queries "
                f"from query_traces"
            )

            # 逐批次执行（traces 模式通常只有一个 batch）
            log_path, log_handler = _setup_eval_log("query_traces")
            results = []
            try:
                for entry in entries:
                    r = await _eval_file_batch(
                        session=session,
                        entry=entry,
                        search_mode=args.search_mode,
                        top_k=args.top_k,
                        rerank=args.rerank,
                        force=args.force,
                    )
                    results.append(r)
            finally:
                sys.stdout.flush()
                log_handler.close()
                sys.stdout = sys.__stdout__
                print(f"\n  Log saved to: {log_path}")

        _print_summary(results)

    # 打印汇总并释放连接
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
