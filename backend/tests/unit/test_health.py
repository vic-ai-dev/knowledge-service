"""健康检查端点测试。"""

import pytest


@pytest.mark.unit
class TestHealth:
    """验证 /api/health 端点工作正常。"""

    async def test_health_returns_ok(self, client):
        """GET /api/health → 200 + status=ok"""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "knowledge-service"
        assert data["version"] == "0.1.0"

    async def test_health_method_not_allowed(self, client):
        """POST /api/health → 405"""
        resp = await client.post("/api/health")
        assert resp.status_code == 405
