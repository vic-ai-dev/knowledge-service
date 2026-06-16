"""Knowledge Service — FastAPI 应用入口。"""

from __future__ import annotations
import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

import time
import uuid
from contextlib import asynccontextmanager
from app.common.telemetry import setup_telemetry

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 导入 factory 包以触发所有工厂注册
import app.factory  # noqa: F401

# 导入 entity 包以触发 declarative base 注册
import app.model.entity  # noqa: F401

from app.common.settings import get_settings
from app.common.log import setup_structlog, get_logger
from app.api.websocket import ingestion_progress_endpoint

_logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    _logger.info(
        "service_startup",
        message="Knowledge Service 正在启动",
    )

    settings = get_settings()

    # ── 初始化数据库连接池 ──
    try:
        from app.common.database_sa import init_sa_engine

        await init_sa_engine()
        _logger.info("sa_engine_ready", message="SQLAlchemy 异步引擎初始化完成")
    except Exception as e:
        _logger.error(
            "sa_engine_failed",
            error=str(e),
            message="SQLAlchemy 异步引擎初始化失败，服务将退出",
        )
        raise

    yield

    # ── 关闭数据库连接池 ──
    try:
        from app.common.database_sa import close_sa_engine

        await close_sa_engine()
        _logger.info("sa_engine_closed", message="SQLAlchemy 引擎已关闭")
    except Exception as e:
        _logger.warning(
            "sa_engine_close_warning",
            message=f"关闭 SA 引擎异常: {e}",
        )

    _logger.info(
        "service_shutdown",
        message="Knowledge Service 正在关闭",
    )


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    # ── 初始化结构化日志（优先于所有模块级日志） ──
    setup_structlog()
    settings = get_settings()

    app = FastAPI(
        title="Knowledge Service",
        description="RAG 知识服务平台 — REST API + MCP SSE Transport",
        version="0.1.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # CORS — 开发环境允许所有 localhost 端口的前端
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── HTTP 访问日志 + request_id 中间件 ─────────────────
    @app.middleware("http")
    async def http_log_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.monotonic()

        _logger.info(
            "http_request",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query_string": str(request.url.query),
                "client_host": request.client.host if request.client else "",
            },
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = time.monotonic() - start
            _logger.error(
                "http_error",
                error=str(exc),
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )

        elapsed = time.monotonic() - start
        response.headers["X-Request-Id"] = request_id

        _logger.info(
            "http_response",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )

        return response

    # ── 健康检查 ──
    @app.get("/api/health")
    async def health():
        """Service health check."""
        return {
            "status": "ok",
            "service": "knowledge-service",
            "version": "0.1.0",
        }

    # ── WebSocket 实时进度推送 ──
    @app.websocket("/api/ws/ingestion/progress")
    async def ws_ingestion_progress(websocket: WebSocket):
        await ingestion_progress_endpoint(websocket)

    # ── 挂载 REST API 路由 ──
    from app.api.router import api_router

    app.include_router(api_router)

    # ── 挂载 MCP SSE Transport ──
    try:
        from app.mcp_server.server import create_mcp_sse_app

        sse_app = create_mcp_sse_app()
        app.mount("/mcp", sse_app)
        _logger.info("mcp_mounted", message="MCP SSE Transport 已挂载到 /mcp")
    except Exception as e:
        _logger.warning(
            "mcp_mount_warning",
            message=f"MCP SSE 挂载失败，服务仍可运行: {e}",
        )

    # ── 初始化 OpenTelemetry ──
    setup_telemetry(app)

    return app


app = create_app()


def main() -> None:
    """启动入口，支持 python app/main.py 直接运行。"""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.server.port,
        reload=getattr(settings.server, "reload", False),
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
