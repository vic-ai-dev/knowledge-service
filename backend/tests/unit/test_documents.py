"""文档仓储级联删除单元测试。

验证 DocumentRepository.cascade_delete() 正确地：
  1. 删除 IngestionHistory（document_id）
  2. 删除 IngestionTrace（document_id）
  3. Soft delete Document（is_deleted=True）
"""

from __future__ import annotations
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
import pytest
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repo import DocumentRepository


pytestmark = pytest.mark.unit


class TestDocumentCascadeDelete:
    """级联删除单元测试 — 验证仓储层的 SQL 调用链。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = MagicMock(spec=AsyncSession)
        execute_mock = AsyncMock(return_value=MagicMock(rowcount=1))
        session.execute = execute_mock
        return session

    @pytest.fixture
    def repo(self, mock_session) -> DocumentRepository:
        return DocumentRepository(mock_session)

    @pytest.mark.asyncio
    async def test_cascade_delete_calls_all_tables(self, repo, mock_session):
        """cascade_delete 应发出 ≥3 条 execute 调用（DELETE x2 + UPDATE x1）。"""
        doc_id = str(uuid.uuid4())
        result = await repo.cascade_delete(doc_id)

        assert result is True
        assert mock_session.execute.call_count >= 3, (
            f"预期 ≥3 次 execute，实际 {mock_session.execute.call_count}"
        )

    @pytest.mark.asyncio
    async def test_cascade_delete_with_uuid(self, repo, mock_session):
        """应接受 uuid.UUID 参数。"""
        doc_id = uuid.uuid4()
        result = await repo.cascade_delete(doc_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_cascade_delete_no_document_returns_false(self, mock_session):
        """无匹配文档时 cascade_delete 返回 False。"""
        mock_session.execute.return_value.rowcount = 0
        repo = DocumentRepository(mock_session)
        result = await repo.cascade_delete(str(uuid.uuid4()))
        assert result is False

    @pytest.mark.asyncio
    async def test_cascade_delete_rollback_on_error(self, repo, mock_session):
        """异常应向上传播给调用方。"""
        mock_session.execute.side_effect = RuntimeError("DB error")
        with pytest.raises(RuntimeError):
            await repo.cascade_delete(str(uuid.uuid4()))


__all__ = ["TestDocumentCascadeDelete"]
