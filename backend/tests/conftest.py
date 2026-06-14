"""pytest 公共配置与 Fixtures。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """FastAPI 测试客户端（ASGI 模式，无需启动服务器）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_settings():
    """返回默认配置字典，用于测试配置加载。"""
    from app.core.settings import Settings
    return Settings()
