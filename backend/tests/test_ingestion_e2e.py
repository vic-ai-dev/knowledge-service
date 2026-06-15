"""E2E 测试：完整文件摄入流程。"""
from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.common.log import setup_structlog
setup_structlog()
from app.common.log import get_logger

logger = get_logger("e2e_test")


async def test_upload_file(file_path: str, category: str = "technical_spec", language: str = "zh"):
    logger.info("e2e_start", metadata={"file": file_path, "category": category, "language": language})

    with open(file_path, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)
    logger.info("e2e_file_info", metadata={"file": file_path, "size": file_size, "hash": file_hash[:16]})

    from app.ingestion.models import IngestionDocument
    doc = IngestionDocument(
        source_path=file_path,
        doc_type=Path(file_path).suffix.lstrip(".").lower(),
        category=category, language=language,
        title=Path(file_path).stem,
        file_size=file_size, file_hash=file_hash,
        collection="default",
    )

    from app.ingestion.pipeline import IngestionPipeline
    pipeline = IngestionPipeline()
    t0 = time.monotonic()
    try:
        result = await pipeline.process_document(doc, force=True)
    except Exception as e:
        logger.error("e2e_pipeline_error", error=str(e))
        raise
    finally:
        await pipeline.close()

    elapsed = (time.monotonic() - t0) * 1000
    logger.info("e2e_complete", metadata={
        "status": result.status.value, "chunks": result.total_chunks,
        "elapsed_ms": round(elapsed, 2), "errors": result.errors,
    })
    return result, file_hash


async def verify_db(file_hash: str, file_path: str, expected_chunks: int):
    """验证数据是否写入 PostgreSQL。"""
    import asyncpg

    # Connect directly
    kb = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='root123456', database='knowledge')
    rag = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='root123456', database='knowledge_rag')
    try:
        # Check ingestion_history
        row = await kb.fetchrow("SELECT id, status, total_chunks FROM ingestion_history WHERE file_hash = $1 ORDER BY created_at DESC LIMIT 1", file_hash)
        if row:
            logger.info("verify_history", metadata={"run_id": str(row["id"]), "status": row["status"], "chunks": row["total_chunks"]})
        else:
            logger.warning("verify_history_missing", metadata={})

        # Check documents
        row2 = await kb.fetchrow("SELECT id, title, chunk_count FROM documents WHERE file_hash = $1", file_hash)
        if row2:
            logger.info("verify_document", metadata={"doc_id": str(row2["id"]), "title": row2["title"], "chunks": row2["chunk_count"]})
        else:
            logger.warning("verify_document_missing", metadata={})

        # Check document_chunks (pgvector)
        rows = await rag.fetch("SELECT id, chunk_index, doc_type, language, category, embedding IS NOT NULL AS has_embedding FROM document_chunks WHERE source_path = $1 LIMIT 3", file_path)
        if rows:
            logger.info("verify_chunks", metadata={"count": len(rows), "has_embedding": all(r["has_embedding"] for r in rows)})
        else:
            logger.warning("verify_chunks_missing", metadata={})
            # Check any chunks in rag
            cnt = await rag.fetchval("SELECT COUNT(*) FROM document_chunks")
            logger.info("verify_rag_total_chunks", metadata={"total_count": cnt})

    finally:
        await kb.close()
        await rag.close()


async def main():
    test_dir = Path("/Users/vic/Documents/知识库/架构文档")
    if not test_dir.exists():
        logger.error("test_dir_not_found", metadata={"path": str(test_dir)})
        return

    files = list(test_dir.glob("*.md")) + list(test_dir.glob("*.html"))
    test_files = files[:3]
    logger.info("e2e_test_files", metadata={"total_available": len(files), "testing": [str(f.name) for f in test_files]})

    results = []
    for f in test_files:
        fname = f.name.lower()
        lang = "zh" if "zh" in fname or "cn" in fname else "en"
        if "架构" in fname or "architecture" in fname:
            cat = "architecture"
        elif "安全" in fname or "security" in fname:
            cat = "compliance"
        elif "微服务" in fname or "microservice" in fname or "ddd" in fname or "domain" in fname:
            cat = "technical_spec"
        else:
            cat = "technical_spec"

        try:
            result, file_hash = await test_upload_file(str(f), category=cat, language=lang)
            await verify_db(file_hash, str(f), result.total_chunks)
            results.append({"file": f.name, "status": result.status.value, "chunks": result.total_chunks})
        except Exception as e:
            logger.error("e2e_file_failed", error=str(e), metadata={"file": f.name})
            import traceback
            traceback.print_exc()
            results.append({"file": f.name, "status": "error", "error": str(e)})

    logger.info("e2e_summary", metadata={"results": results})
    print("\n\n=== E2E TEST SUMMARY ===")
    for r in results:
        print(f"  {r['file']}: {r['status']} ({r.get('chunks', 0)} chunks)")
    print("========================\n")


if __name__ == "__main__":
    asyncio.run(main())
