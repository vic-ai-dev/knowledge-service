"""E9 — WebSocket 实时进度推送。

为 Ingestion Pipeline 提供 WebSocket 进度推送。
连接端点：/api/ws/ingestion/progress
消息格式：JSON (PipelineProgress)
"""

from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect
from app.common.log import get_logger
from app.common.pipeline_callback import PipelineProgress, ProgressCallback

logger = get_logger(__name__)


class WebSocketProgressManager:
    """WebSocket 进度推送管理器。

    维护活跃 WebSocket 连接集合，向所有连接广播进度更新。
    """

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """接受新的 WebSocket 连接。"""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(
            "ws_connected",
            message="WebSocket 客户端已连接",
            metadata={"active_connections": len(self._connections)},
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除断开的 WebSocket 连接。"""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(
            "ws_disconnected",
            message="WebSocket 客户端已断开",
            metadata={"active_connections": len(self._connections)},
        )

    async def broadcast(self, progress: PipelineProgress) -> None:
        """向所有活跃连接广播进度消息。"""
        if not self._connections:
            return

        payload = {
            "run_id": progress.run_id,
            "stage": progress.stage.value,
            "progress": progress.progress,
            "message": progress.message,
            "total": progress.total,
            "current": progress.current,
            "metadata": progress.metadata,
        }
        message = json.dumps(payload, ensure_ascii=False)

        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._connections.discard(ws)

    def create_callback(self) -> ProgressCallback:
        """创建一个可通过 Pipeline 调用的进度回调。"""
        manager = self

        def callback(progress: PipelineProgress) -> None:
            """进度回调函数（同步，广播用 ensure_future 异步执行）。"""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(manager.broadcast(progress))
            except RuntimeError:
                pass

        return callback


# ── 全局单例 ───────────────────────────────────────────

progress_manager = WebSocketProgressManager()


# ── FastAPI WebSocket 端点 ────────────────────────────


async def ingestion_progress_endpoint(websocket: WebSocket) -> None:
    """Ingestion Pipeline 进度 WebSocket 端点。

    客户端连接后保持长连接，服务器推送 JSON 进度消息。
    """
    await progress_manager.connect(websocket)
    try:
        # 保持连接，等待客户端断开
        while True:
            # 接收客户端消息（ping/pong 或关闭）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(
            "ws_error",
            message=f"WebSocket 连接异常: {e}",
        )
    finally:
        await progress_manager.disconnect(websocket)


__all__ = [
    "WebSocketProgressManager",
    "progress_manager",
    "ingestion_progress_endpoint",
]
