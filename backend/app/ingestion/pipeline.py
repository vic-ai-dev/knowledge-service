"""C14 — IngestionPipeline：数据摄取管线编排器。

完整摄入流程：
  1. FileIntegrityChecker — SHA256 去重检查
  2. FileIntegrityChecker.register() — 注册摄入任务
  3. BatchProcessor.process_document() — Load → Split → Transform → Embed
  4. VectorUpserter.upsert() — 写入 pgvector（tsvector 由 PostgreSQL GENERATED 列自动填充）
  5. FileIntegrityChecker.update_status() — 更新摄入状态
  6. 返回 IngestionResult（含嵌入式 Chunk 列表和各阶段耗时）
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.ingestion.chunking.batch_processor import BatchProcessor
from app.ingestion.embedding.dense_encoder import DenseEncoder
from app.ingestion.integrity import FileIntegrityChecker, IntegrityCheckResult
from app.ingestion.models import (
    IngestionDocument,
    IngestionResult,
    IngestionStatus,
)
from app.ingestion.storage.vector_upserter import VectorUpserter
from app.libs.base.base_llm import BaseLLM
from app.common.log import get_logger
from app.observability.instrumentation import trace_span
from app.observability.progress import (
    NoOpProgressCallback,
    ProgressCallback,
)

logger = get_logger(__name__)


class IngestionPipelineError(RuntimeError):
    """IngestionPipeline 通用异常。"""
    pass


class IngestionPipeline:
    """数据摄取管线编排器。

    整合 Integrity → BatchProcess → VectorUpsert 三步流程，
    提供单文档和批量文档的摄取接口。

    :param batch_processor: BatchProcessor 实例（默认创建）。
    :param vector_upserter: VectorUpserter 实例（默认创建）。
    :param integrity_checker: FileIntegrityChecker 实例（默认创建）。
    :param progress_callback: 进度回调函数。
    :param llm: MetadataEnricher 使用的 LLM（可选，默认 DenseEncoder 内置）。
    """

    def __init__(
        self,
        batch_processor: BatchProcessor | None = None,
        vector_upserter: VectorUpserter | None = None,
        integrity_checker: FileIntegrityChecker | None = None,
        progress_callback: ProgressCallback | None = None,
        llm: BaseLLM | None = None,
    ):
        self._progress = progress_callback or NoOpProgressCallback()
        self._integrity = integrity_checker or FileIntegrityChecker()
        self._vector_upserter = vector_upserter or VectorUpserter()
        self._llm = llm
        self._batch_processor = batch_processor or BatchProcessor(
            dense_encoder=DenseEncoder(),
            progress_callback=self._progress,
        )

    # ── 输入校验 ──

    def _validate_document(self, doc: IngestionDocument) -> None:
        if not doc.source_path and not doc.text:
            raise IngestionPipelineError("document must have source_path or text")
        if doc.doc_type not in ("pdf", "md", "html"):
            raise IngestionPipelineError(
                f"unsupported doc_type: {doc.doc_type} (pdf/md/html)"
            )

    # ── 核心方法 ──

    @trace_span()
    async def process_document(
        self,
        doc: IngestionDocument,
        force: bool = False,
    ) -> IngestionResult:
        """处理单篇文档。

        Args:
            doc: 待处理的文档。
            force: 为 True 时跳过完整性检查（强制重新处理）。

        Returns:
            IngestionResult — 包含摄入状态、Chunk 列表、各阶段指标。
        """
        self._validate_document(doc)

        # ── 1. 完整性检查 ──────────────────────────────────
        if not force and doc.source_path:
            path = Path(doc.source_path)
            if path.exists():
                check: IntegrityCheckResult = await self._integrity.check_file(
                    path
                )
                if not check.should_process:
                    logger.info(
                        "pipeline_skip_duplicate",
                        metadata={
                            "source_path": doc.source_path,
                            "file_hash": check.file_hash,
                            "message": check.message,
                        },
                    )
                    return IngestionResult(
                        source_path=doc.source_path,
                        status=IngestionStatus.SKIPPED,
                        total_chunks=0,
                    )
                doc.file_hash = check.file_hash

        # ── 2. 生成文档 ID 并注册 ──────────────────────────
        document_id = str(uuid.uuid4())
        doc_id_short = document_id.split("-")[0]

        if doc.source_path:
            run_id = await self._integrity.register(
                source_path=doc.source_path,
                file_hash=doc.file_hash or "",
                document_id=document_id,
                category=doc.category,
                language=doc.language or "",
                doc_type=doc.doc_type,
                file_size=doc.file_size or 0,
            )
        else:
            run_id = str(uuid.uuid4())

        # ── 3. BatchProcessor 处理（Load → Split → Transform → Embed） ──
        batch_result = await self._batch_processor.process_document(
            doc=doc,
            run_id=run_id,
        )

        if batch_result.status != IngestionStatus.COMPLETED:
            # 更新数据库状态为失败
            if doc.source_path:
                await self._integrity.update_status(
                    run_id=run_id,
                    status="failed",
                    error_message="; ".join(batch_result.errors),
                )
            return batch_result

        chunks = batch_result.chunks

        # ── 3.5 回填 document_id ────────────────────────────
        # BatchProcessor 生成 chunks 时不知道 document_id，
        # 需要在这里回填后再写入存储层。
        for chunk in chunks:
            chunk.document_id = document_id

        # ── 4. VectorUpserter 写入 pgvector ─────────────────
        if chunks:
            try:
                upserted_count = await self._vector_upserter.upsert(chunks)
                logger.info(
                    "pipeline_vector_upsert_done",
                    metadata={
                        "run_id": run_id,
                        "document_id": document_id,
                        "upserted": upserted_count,
                        "total_chunks": len(chunks),
                    },
                )
            except Exception as e:
                batch_result.status = IngestionStatus.FAILED
                batch_result.errors.append(f"vector_upsert failed: {e}")
                if doc.source_path:
                    await self._integrity.update_status(
                        run_id=run_id,
                        status="failed",
                        error_message=str(e),
                    )
                return batch_result

        # ── 5. 更新摄入状态 ─────────────────────────────────
        batch_result.document_id = document_id

        # ── 6. 写入 documents 表 ────────────────────────────
        if doc.source_path:
            try:
                await self._integrity.register_document(
                    document_id=document_id,
                    source_path=doc.source_path,
                    title=doc.title,
                    collection=doc.collection,
                    category=doc.category,
                    language=doc.language or "",
                    doc_type=doc.doc_type,
                    file_size=doc.file_size or 0,
                    file_hash=doc.file_hash or "",
                    chunk_count=len(chunks),
                )
                logger.info(
                    "pipeline_document_registered",
                    metadata={
                        "document_id": document_id,
                        "source_path": doc.source_path,
                        "chunk_count": len(chunks),
                    },
                )
            except Exception as e:
                logger.warning(
                    "pipeline_document_register_warn",
                    error=str(e),
                    metadata={"document_id": document_id},
                )

        # ── 7. 写入 ingestion_traces 表 ──────────────────────
        if doc.source_path:
            try:
                stage_data = [
                    {
                        "stage": s.stage,
                        "duration_ms": round(s.duration_ms, 2),
                        "items": s.items_processed,
                    }
                    for s in batch_result.stages
                ]
                await self._integrity.record_ingestion_trace(
                    source_path=doc.source_path,
                    collection=doc.collection,
                    total_latency_ms=sum(s.duration_ms for s in batch_result.stages),
                    status=batch_result.status.value,
                    total_chunks=len(chunks),
                    stages=stage_data,
                    error="; ".join(batch_result.errors) if batch_result.errors else None,
                )
                logger.info(
                    "pipeline_trace_recorded",
                    metadata={
                        "run_id": run_id,
                        "source_path": doc.source_path,
                        "total_chunks": len(chunks),
                    },
                )
            except Exception as e:
                logger.warning(
                    "pipeline_trace_warning",
                    error=str(e),
                    metadata={"source_path": doc.source_path},
                )

        # ── 8. 更新摄入状态 ───────────────────────────────────
        if doc.source_path:
            await self._integrity.update_status(
                run_id=run_id,
                status="completed",
                total_chunks=len(chunks),
            )

        logger.info(
            "pipeline_process_done",
            metadata={
                "run_id": run_id,
                "document_id": doc_id_short,
                "source_path": doc.source_path,
                "status": batch_result.status.value,
                "total_chunks": len(chunks),
                "stages": [s.stage for s in batch_result.stages],
            },
        )

        return batch_result

    @trace_span()
    async def process_batch(
        self,
        documents: list[IngestionDocument],
    ) -> list[IngestionResult]:
        """批量处理多篇文档。

        Args:
            documents: 待处理的文档列表。

        Returns:
            摄入结果列表（每篇文档对应一个 IngestionResult）。
        """
        results: list[IngestionResult] = []
        for i, doc in enumerate(documents):
            logger.info(
                "pipeline_batch_progress",
                metadata={
                    "doc_index": i,
                    "total": len(documents),
                    "source_path": doc.source_path,
                },
            )
            result = await self.process_document(doc)
            results.append(result)
        return results

    async def close(self) -> None:
        """释放连接池资源。"""
        await self._integrity.close()
        if self._vector_upserter._store:
            await self._vector_upserter._store.close()


__all__ = ["IngestionPipeline", "IngestionPipelineError"]
