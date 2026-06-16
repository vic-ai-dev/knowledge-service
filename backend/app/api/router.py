"""API 路由聚合 — 所有 REST 端点在此注册。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.system import router as system_router
from app.api.data import router as data_router
from app.api.ingestion import router as ingestion_router
from app.api.query import router as query_router
from app.api.documents import router as documents_router
from app.api.evaluation import router as evaluation_router
from app.api.images import router as images_router

# ── 主 API 路由器 ─────────────────────────────────────

api_router = APIRouter(prefix="/api")

# 注册各模块路由
api_router.include_router(system_router)
api_router.include_router(data_router)
api_router.include_router(ingestion_router)
api_router.include_router(query_router)
api_router.include_router(documents_router)
api_router.include_router(evaluation_router)
api_router.include_router(images_router)


__all__ = ["api_router"]
