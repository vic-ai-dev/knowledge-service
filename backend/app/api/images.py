"""E8 — 图片服务端点。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.common.log import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_id}")
async def get_image(image_id: str):
    """获取图片文件。"""
    # TODO(E8): 从存储读取图片
    raise HTTPException(status_code=404, detail="Image not found")


@router.get("/{image_id}/metadata")
async def get_image_metadata(image_id: str):
    """获取图片元数据。"""
    # TODO(E8): 从数据库读取图片元数据
    raise HTTPException(status_code=404, detail="Image not found")


__all__ = ["router"]
