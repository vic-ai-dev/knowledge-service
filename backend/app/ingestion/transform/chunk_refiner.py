"""C5 — ChunkRefiner：Chunk 文本清洗与规范化。

职责：
  1. 去除空 Chunk（文本长度 < min_length 的丢弃）
  2. 规范化空白字符（制表符→空格、连续空白→单空格）
  3. 去除首尾空白
  4. 修复常见编码问题（控制字符清除）
  5. 更新 token_count 估算
"""

from __future__ import annotations

import re
from typing import Any

from app.ingestion.models import ChunkRecord
from app.ingestion.transform.base import BaseTransform, TransformError
from app.observability import get_logger

logger = get_logger(__name__)

# 控制字符（保留换行符和制表符）
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# 连续空白（空格、制表符等）→ 单空格
_WHITESPACE_RE = re.compile(r"[ \t]+")
# 连续空行（3行以上）→ 最多2行
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


class ChunkRefiner(BaseTransform):
    """Chunk 文本清洗与规范化。

    :param min_length: Chunk 最小字符数，低于此值的 Chunk 将被过滤。
    :param max_length: Chunk 最大字符数，超过此值的将截断（0=不截断）。
    """

    def __init__(self, min_length: int = 10, max_length: int = 0):
        self._min_length = min_length
        self._max_length = max_length

    def _normalize_whitespace(self, text: str) -> str:
        """规范化空白字符。"""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _CONTROL_CHARS_RE.sub("", text)
        text = _WHITESPACE_RE.sub(" ", text)
        text = _MULTI_BLANK_RE.sub("\n\n", text)
        return text.strip()

    def _estimate_tokens(self, text: str) -> int:
        """近似估算 Token 数量。"""
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_chars = len(text) - chinese
        return int(ascii_chars / 4 + chinese / 1.5) + 1

    async def transform(
        self,
        chunks: list[ChunkRecord],
        **kwargs: Any,
    ) -> list[ChunkRecord]:
        """执行 Chunk 清洗。"""
        if not chunks:
            return chunks

        refined: list[ChunkRecord] = []
        filtered_count = 0
        truncated_count = 0

        for chunk in chunks:
            if not chunk.text:
                filtered_count += 1
                continue

            normalized = self._normalize_whitespace(chunk.text)

            if len(normalized) < self._min_length:
                filtered_count += 1
                continue

            if self._max_length > 0 and len(normalized) > self._max_length:
                normalized = normalized[:self._max_length]
                truncated_count += 1

            chunk.text = normalized
            chunk.token_count = self._estimate_tokens(normalized)
            refined.append(chunk)

        if filtered_count > 0 or truncated_count > 0:
            logger.info(
                "chunk_refiner",
                event_type="splitting",
                metadata={
                    "input_count": len(chunks),
                    "output_count": len(refined),
                    "filtered": filtered_count,
                    "truncated": truncated_count,
                },
            )

        return refined
