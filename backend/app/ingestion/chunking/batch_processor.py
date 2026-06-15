"""C10 — BatchProcessor：文档摄入批处理器。

编排单篇文档的摄入管线：
  1. Load（通过 LoaderFactory 按 doc_type 加载）
  2. Split（通过 SplitterFactory 按 doc_type 分块）
  3. Transform（ChunkRefiner → MetadataEnricher）
  4. Embed（DenseEncoder 稠密编码）
  5. 进度回调（ProgressCallback）

返回结构化指标（IngestionResult），包括各阶段耗时与错误信息。
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.ingestion.embedding.dense_encoder import DenseEncoder
from app.ingestion.models import (
    ChunkRecord,
    IngestionDocument,
    IngestionResult,
    IngestionStatus,
    StageMetrics,
)
from app.ingestion.transform.chunk_refiner import ChunkRefiner
from app.ingestion.transform.metadata_enricher import MetadataEnricher
from app.libs.factory import LoaderFactory, SplitterFactory
from app.common.log import get_logger
from app.observability.instrumentation import trace_span
from app.observability.progress import (
    NoOpProgressCallback,
    PipelineProgress,
    PipelineStage,
    ProgressCallback,
)

logger = get_logger(__name__)


class BatchProcessorError(RuntimeError):
    """BatchProcessor 通用异常。"""
    pass


class BatchProcessor:
    """文档摄入批处理器。

    编排单篇文档从加载到向量化的完整管线，支持进度回调。

    :param dense_encoder: DenseEncoder 实例，用于向量编码。
    :param chunk_refiner: ChunkRefiner 实例（默认使用默认参数构造）。
    :param metadata_enricher: MetadataEnricher 实例（默认使用默认参数构造）。
    :param progress_callback: 进度回调函数。
    """

    def __init__(
        self,
        dense_encoder: DenseEncoder,
        chunk_refiner: ChunkRefiner | None = None,
        metadata_enricher: MetadataEnricher | None = None,
        progress_callback: ProgressCallback | None = None,
    ):
        self._dense_encoder = dense_encoder
        self._chunk_refiner = chunk_refiner or ChunkRefiner()
        self._metadata_enricher = metadata_enricher or MetadataEnricher()
        self._progress = progress_callback or NoOpProgressCallback()

    # ── 输入校验 ──

    def _validate_document(self, doc: IngestionDocument) -> None:
        if not doc.source_path and not doc.text:
            raise BatchProcessorError("document must have source_path or text")
        if doc.doc_type not in ("pdf", "md", "html"):
            raise BatchProcessorError(
                f"unsupported doc_type: {doc.doc_type} (pdf/md/html)"
            )

    # ── 记录阶段指标 ──

    def _record_stage(
        self,
        result: IngestionResult,
        stage_name: str,
        duration_ms: float,
        items: int = 0,
        error: str | None = None,
    ) -> None:
        result.stages.append(StageMetrics(
            stage=stage_name,
            duration_ms=duration_ms,
            items_processed=items,
            error=error,
        ))

    # ── SplitResult → ChunkRecord 转换 ──

    @staticmethod
    def _convert_to_chunk_record(
        sr,
        doc: IngestionDocument,
    ) -> ChunkRecord:
        """将 SplitResult 转换为 ChunkRecord，注入文档级元数据。"""
        from app.libs.base.base_splitter import SplitResult

        if not isinstance(sr, SplitResult):
            raise BatchProcessorError(f"expected SplitResult, got {type(sr)}")

        return ChunkRecord(
            chunk_id=str(uuid.uuid4()),
            text=sr.text,
            metadata={
                **sr.metadata,
                **doc.metadata,
            },
            chunk_index=sr.chunk_index,
            source_path=doc.source_path,
            collection=doc.collection,
            category=doc.category,
            language=doc.language,
            doc_type=doc.doc_type,
        )

    # ── 核心方法 ──

    @trace_span("ingestion", "batch_processor")
    async def process_document(
        self,
        doc: IngestionDocument,
        run_id: str | None = None,
    ) -> IngestionResult:
        """处理单篇文档。

        Args:
            doc: 待处理的文档描述（source_path / text + 元数据）。
            run_id: 运行 ID（不提供则自动生成）。

        Returns:
            摄入结果（含各阶段指标与最终状态）。
        """
        self._validate_document(doc)
        run_id = run_id or str(uuid.uuid4())

        result = IngestionResult(
            run_id=run_id,
            source_path=doc.source_path,
            status=IngestionStatus.RUNNING,
        )

        self._progress(PipelineProgress(
            run_id=run_id,
            stage=PipelineStage.LOADING,
            progress=0.0,
            message=f"Starting: {doc.source_path}",
        ))

        try:
            # ── 1. Load ──────────────────────────────────────
            t0 = time.monotonic()
            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.LOADING,
                progress=0.1,
                message=f"Loading {doc.source_path}",
            ))

            loader = LoaderFactory.create(doc.doc_type)
            if doc.text:
                # 文本已提供，不做加载
                load_results = []
                from app.libs.base.base_loader import LoadResult
                load_results.append(LoadResult(
                    text=doc.text,
                    metadata=dict(doc.metadata),
                    source_path=doc.source_path,
                ))
            else:
                load_results = await loader.load(doc.source_path)

            self._record_stage(
                result, "load",
                (time.monotonic() - t0) * 1000,
                items=len(load_results),
            )

            # ── 2. Split ─────────────────────────────────────
            t0 = time.monotonic()
            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.SPLITTING,
                progress=0.3,
                message="Splitting document into chunks",
            ))

            splitter = SplitterFactory.create_for_doc_type(doc.doc_type)
            split_results = []
            for lr in load_results:
                splits = splitter.split(lr.text, metadata=lr.metadata)
                split_results.extend(splits)

            self._record_stage(
                result, "split",
                (time.monotonic() - t0) * 1000,
                items=len(split_results),
            )

            # ── 3. Convert to ChunkRecords ───────────────────
            chunks = [
                self._convert_to_chunk_record(sr, doc)
                for sr in split_results
            ]

            if not chunks:
                raise BatchProcessorError("no chunks produced from document")

            # ── 4. Transform ─────────────────────────────────
            t0 = time.monotonic()
            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.TRANSFORMING,
                progress=0.5,
                message=f"Transforming {len(chunks)} chunks",
                total=len(chunks),
            ))

            chunks = await self._chunk_refiner(chunks)
            document_meta = {
                "source_path": doc.source_path,
                "collection": doc.collection,
                "category": doc.category,
                "language": doc.language,
                "doc_type": doc.doc_type,
                "title": doc.title or "",
            }
            chunks = await self._metadata_enricher(
                chunks, document_meta=document_meta,
            )

            self._record_stage(
                result, "transform",
                (time.monotonic() - t0) * 1000,
                items=len(chunks),
            )

            # ── 5. Embed ─────────────────────────────────────
            t0 = time.monotonic()
            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.EMBEDDING,
                progress=0.7,
                message=f"Embedding {len(chunks)} chunks",
                total=len(chunks),
            ))

            chunks = await self._dense_encoder.encode(chunks)

            self._record_stage(
                result, "embed",
                (time.monotonic() - t0) * 1000,
                items=len(chunks),
            )

            # ── Complete ─────────────────────────────────────
            result.status = IngestionStatus.COMPLETED
            result.total_chunks = len(chunks)
            result.chunks = chunks

            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.COMPLETED,
                progress=1.0,
                message=f"Completed: {doc.source_path} ({len(chunks)} chunks)",
                total=len(chunks),
            ))

            logger.info(
                "batch_processor_done",
                event_type="ingestion",
                metadata={
                    "run_id": run_id,
                    "source_path": doc.source_path,
                    "chunks": len(chunks),
                    "stages": [s.stage for s in result.stages],
                },
            )

        except Exception as e:
            result.status = IngestionStatus.FAILED
            result.errors.append(str(e))
            self._progress(PipelineProgress(
                run_id=run_id,
                stage=PipelineStage.FAILED,
                progress=1.0,
                message=f"Failed: {e}",
            ))
            logger.error(
                "batch_processor_error",
                event_type="ingestion",
                error=str(e),
                metadata={"run_id": run_id, "source_path": doc.source_path},
            )

        return result

    @trace_span("ingestion", "batch_processor_batch")
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
                "batch_processor_progress",
                event_type="ingestion",
                metadata={
                    "doc_index": i,
                    "total": len(documents),
                    "source_path": doc.source_path,
                },
            )
            result = await self.process_document(doc)
            results.append(result)
        return results


__all__ = ["BatchProcessor", "BatchProcessorError"]
