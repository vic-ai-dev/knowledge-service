"""Knowledge Service — FastAPI 应用入口。"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 导入 libs 包以触发所有工厂注册
import app.libs  # noqa: F401

# 导入 models 包以触发 declarative base 注册
import app.models  # noqa: F401

from app.core.settings import get_settings
from app.common.log import setup_structlog, get_logger
from app.core.trace import trace_context, generate_id, get_trace_context
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
        from app.core.database_sa import init_sa_engine

        await init_sa_engine()
        _logger.info("sa_engine_ready", message="SQLAlchemy 异步引擎初始化完成")
    except Exception as e:
        _logger.error(
            "sa_engine_failed",
            error=str(e),
            message="SQLAlchemy 异步引擎初始化失败，服务将退出",
        )
        raise

    # ── 初始化 asyncpg 连接池（过渡期兼容，失败不阻塞）──
    try:
        from app.core.database import init_db_pools

        await init_db_pools()
        _logger.info("db_pools_ready", message="asyncpg 连接池初始化完成（过渡期兼容）")
    except Exception as e:
        _logger.warning(
            "db_pool_skip",
            error=str(e),
            message="asyncpg 连接池初始化跳过 — 已迁移至 SA，可安全忽略",
        )

    yield

    # ── 关闭数据库连接池 ──
    try:
        from app.core.database_sa import close_sa_engine

        await close_sa_engine()
        _logger.info("sa_engine_closed", message="SQLAlchemy 引擎已关闭")
    except Exception as e:
        _logger.warning(
            "sa_engine_close_warning",
            message=f"关闭 SA 引擎异常: {e}",
        )

    try:
        from app.core.database import close_db_pools

        await close_db_pools()
    except Exception as e:
        _logger.warning(
            "db_close_warning",
            message=f"关闭数据库连接时出现异常: {e}",
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

    # ── 注册 tracing + request_id 中间件 ──
    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", "")
        parent_span_id = request.headers.get("X-Span-Id", "")
        request_id = request.headers.get("X-Request-Id", generate_id())

        start = time.monotonic()

        with trace_context(
            trace_id=trace_id or None,
            parent_span_id=parent_span_id or None,
            request_id=request_id,
            enabled=settings.observability.tracing.enabled,
        ):
            ctx = get_trace_context()

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

            if ctx.get("trace_id"):
                response.headers["X-Trace-Id"] = ctx["trace_id"]
            if ctx.get("span_id"):
                response.headers["X-Span-Id"] = ctx["span_id"]
            if ctx.get("request_id"):
                response.headers["X-Request-Id"] = ctx["request_id"]

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
