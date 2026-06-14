"""Knowledge Service — FastAPI 应用入口。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    settings = get_settings()
    # TODO(A3): 初始化数据库连接池
    # TODO(F4): request_id 中间件
    yield
    # TODO: 清理资源


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()

    app = FastAPI(
        title="Knowledge Service",
        description="RAG 知识服务平台 — REST API + MCP SSE Transport",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — 允许前端开发服务器访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 健康检查 ──
    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "service": "knowledge-service",
            "version": "0.1.0",
        }

    # TODO(E 阶段): 挂载 REST API 路由
    # TODO(E 阶段): 挂载 MCP SSE Transport
    # TODO(E 阶段): 挂载 WebSocket 端点

    return app


app = create_app()


def main() -> None:
    """启动入口，支持 python app/main.py 直接运行。"""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.server.port,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    main()
