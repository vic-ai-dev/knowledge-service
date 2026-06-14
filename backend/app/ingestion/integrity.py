"""C2 — File Integrity Checker (SHA256 + PostgreSQL 去重).

负责：
  1. 异步计算文件 SHA256 哈希值
  2. 通过 PostgreSQL ingestion_history 表检查文件是否已摄入
  3. 为新文件注册摄取任务
  4. 更新摄入状态
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import asyncpg

from app.core.settings import get_settings
from app.ingestion.models import IngestionStatus
from app.observability.instrumentation import trace_span
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class IntegrityCheckResult:
    """文件完整性检查结果。"""

    file_hash: str
    should_process: bool  # True=新文件或上次失败, False=已完成跳过
    existing_run_id: str | None = None
    previous_status: str | None = None
    message: str = ""


def _compute_sha256_sync(path: str) -> str:
    """同步 SHA256 计算（在线程池中执行）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class FileIntegrityChecker:
    """文件完整性检查器。

    使用 SHA256 哈希 + PostgreSQL ingestion_history 表实现文件级去重。
    
    用法:
        checker = FileIntegrityChecker()
        result = await checker.check_file("/path/to/doc.pdf")
        if result.should_process:
            run_id = await checker.register(path, result.file_hash, doc_id)
            # ... 执行摄取 ...
            await checker.update_status(run_id, "completed", total_chunks=42)
        await checker.close()
    """

    def __init__(self, pool: asyncpg.Pool | None = None):
        self._pool = pool
        self._own_pool = False

    async def _ensure_pool(self) -> asyncpg.Pool:
        """获取或创建 asyncpg 连接池。"""
        if self._pool is not None:
            return self._pool

        settings = get_settings()
        dsn = (
            f"postgresql://{settings.database.user}:{settings.database.password}"
            f"@{settings.database.host}:{settings.database.port}"
            f"/{settings.database.database}"
        )
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=2,
        )
        self._own_pool = True
        return self._pool

    async def close(self) -> None:
        """关闭连接池（仅当由本实例创建时）。"""
        if self._own_pool and self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ── 公开方法 ──────────────────────────────────────

    @staticmethod
    async def compute_sha256(path: str | Path) -> str:
        """异步计算文件 SHA256 哈希值。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _compute_sha256_sync, str(path))

    @trace_span("retrieval", "integrity_check")
    async def check_file(self, path: str | Path) -> IntegrityCheckResult:
        """检查文件是否已摄入。

        1. 计算文件 SHA256 哈希
        2. 查询 PostgreSQL ingestion_history 表
        3. 返回检查结果（跳过 / 重新处理 / 新文件）
        """
        path_str = str(path)
        file_hash = await self.compute_sha256(path_str)
        pool = await self._ensure_pool()

        logger.info(
            "integrity_check",
            event_type="retrieval",
            metadata={"file_path": path_str, "file_hash": file_hash},
        )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, status FROM ingestion_history
                   WHERE file_hash = $1
                   ORDER BY created_at DESC LIMIT 1""",
                file_hash,
            )

            if row is None:
                logger.info(
                    "integrity_check_new",
                    event_type="retrieval",
                    metadata={"file_path": path_str, "result": "new"},
                )
                return IntegrityCheckResult(
                    file_hash=file_hash,
                    should_process=True,
                    message="新文件，需要处理",
                )

            prev_status = row["status"]
            if prev_status == "completed":
                logger.info(
                    "integrity_check_skip",
                    event_type="retrieval",
                    metadata={
                        "file_path": path_str,
                        "result": "skipped",
                        "run_id": row["id"],
                    },
                )
                return IntegrityCheckResult(
                    file_hash=file_hash,
                    should_process=False,
                    existing_run_id=row["id"],
                    previous_status=prev_status,
                    message="文件内容未变更，跳过",
                )

            # 上次失败 / 未完成 → 允许重新处理
            logger.info(
                "integrity_check_retry",
                event_type="retrieval",
                metadata={
                    "file_path": path_str,
                    "result": "retry",
                    "previous_status": prev_status,
                },
            )
            return IntegrityCheckResult(
                file_hash=file_hash,
                should_process=True,
                existing_run_id=row["id"],
                previous_status=prev_status,
                message=f"上次状态为 {prev_status}，重新处理",
            )

    @trace_span("retrieval", "integrity_register")
    async def register(
        self,
        source_path: str,
        file_hash: str,
        document_id: str,
    ) -> str:
        """注册新文件到 ingestion_history 表。

        Returns:
            新创建的 run_id (UUID 字符串)
        """
        pool = await self._ensure_pool()
        run_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ingestion_history (id, document_id, source_path, file_hash)
                   VALUES ($1, $2, $3, $4)""",
                run_id,
                document_id,
                source_path,
                file_hash,
            )

        logger.info(
            "integrity_register",
            event_type="retrieval",
            metadata={
                "run_id": run_id,
                "file_path": source_path,
                "file_hash": file_hash,
            },
        )
        return run_id

    @trace_span("retrieval", "integrity_update")
    async def update_status(
        self,
        run_id: str,
        status: str,
        total_chunks: int = 0,
        total_images: int = 0,
        error_message: str | None = None,
    ) -> None:
        """更新 ingestion_history 记录的状态。"""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            if status in ("completed", "failed"):
                await conn.execute(
                    """UPDATE ingestion_history
                       SET status = $1, total_chunks = $2, total_images = $3,
                           error_message = $4, completed_at = NOW()
                       WHERE id = $5""",
                    status,
                    total_chunks,
                    total_images,
                    error_message,
                    run_id,
                )
            else:
                await conn.execute(
                    """UPDATE ingestion_history
                       SET status = $1, started_at = NOW()
                       WHERE id = $2""",
                    status,
                    run_id,
                )

        logger.info(
            "integrity_update",
            event_type="retrieval",
            metadata={
                "run_id": run_id,
                "status": status,
                "total_chunks": total_chunks,
            },
        )

    @trace_span("retrieval", "integrity_get_document_id")
    async def get_document_id_by_hash(self, file_hash: str) -> str | None:
        """通过 file_hash 查找已关联的 document_id。"""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT document_id FROM ingestion_history WHERE file_hash = $1 LIMIT 1",
                file_hash,
            )
            return str(row["document_id"]) if row else None


__all__ = [
    "FileIntegrityChecker",
    "IntegrityCheckResult",
    "IntegrityCheckResult",
]
