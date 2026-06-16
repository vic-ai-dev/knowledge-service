"""PDFLoader 单元测试 — 验证 PDF 文件加载与结构化文本提取。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.factory.loader.pdf import PDFLoader


pytestmark = pytest.mark.unit

_TEST_PDF = Path("/Users/vic/Documents/知识库/PDF输出/CICD_Standard_en.pdf")


class TestPDFLoader:
    """PDFLoader 加载功能验证。"""

    @pytest.fixture
    def loader(self) -> PDFLoader:
        return PDFLoader()

    @pytest.fixture
    def pdf_copy(self) -> Path:
        """将测试 PDF 复制到临时目录。"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            dst = Path(tmp.name)
        shutil.copy2(_TEST_PDF, dst)
        yield dst
        dst.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_returns_results(self, loader, pdf_copy):
        """load() 返回包含非空文本的 LoadResult。"""
        results = await loader.load(pdf_copy)
        assert len(results) == 1
        result = results[0]
        assert result.text, "转换后的文本不应为空"
        assert len(result.text) > 100

    @pytest.mark.asyncio
    async def test_load_metadata(self, loader, pdf_copy):
        """LoadResult.metadata 应包含 source_path。"""
        results = await loader.load(pdf_copy)
        meta = results[0].metadata
        assert "source_path" in meta
        assert str(pdf_copy) in meta["source_path"]

    @pytest.mark.asyncio
    async def test_load_content_meaningful(self, loader, pdf_copy):
        """提取的文本应包含文档的关键术语。"""
        results = await loader.load(pdf_copy)
        text = results[0].text.lower()
        keywords = ["ci/cd", "cicd", "continuous", "pipeline", "deployment", "integration"]
        assert any(k in text for k in keywords), f"文本中未找到预期关键词: {keywords[:3]}"

    @pytest.mark.asyncio
    async def test_load_preserves_structure(self, loader, pdf_copy):
        """段落/标题结构应被 Markdown 转换保留。"""
        results = await loader.load(pdf_copy)
        text = results[0].text
        assert "#" in text or "\n\n" in text, "转换结果缺少标题或段落结构"

    @pytest.mark.asyncio
    async def test_load_non_pdf_no_exception(self, loader):
        """非 PDF 文件不会抛异常（markitdown 处理为文本）。"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"not a real pdf content")
            fake = Path(f.name)
        try:
            results = await loader.load(fake)
            assert isinstance(results, list)
        finally:
            fake.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_nonexistent_file_raises(self, loader):
        """不存在的文件应抛出异常。"""
        with pytest.raises(Exception):
            await loader.load("/tmp/does_not_exist_12345.pdf")


__all__ = ["TestPDFLoader"]
