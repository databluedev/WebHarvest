"""Integration tests for /health and /health/ready endpoints."""

import pytest
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


class TestLivenessEndpoint:
    @pytest.mark.asyncio
    async def test_liveness_returns_healthy(self, client: AsyncClient):
        """GET /health returns 200 with status healthy."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestReadinessEndpoint:
    @pytest.mark.asyncio
    async def test_readiness_checks_all_services(self, client: AsyncClient):
        """GET /health/ready returns check results for DB, Redis, and browser pool."""
        with (
            patch("app.core.database.engine") as mock_engine,
            patch("app.core.redis.redis_client") as mock_redis,
            patch("app.services.browser.browser_pool") as mock_bp,
        ):
            # Mock successful checks
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_engine.connect.return_value = mock_ctx

            mock_redis.ping = AsyncMock()
            mock_bp._initialized = True

            resp = await client.get("/health/ready")
            data = resp.json()
            assert "checks" in data

    @pytest.mark.asyncio
    async def test_readiness_returns_503_on_failure(self, client: AsyncClient):
        """GET /health/ready returns 503 when a service check fails."""
        with (
            patch("app.core.database.engine") as mock_engine,
            patch("app.core.redis.redis_client") as mock_redis,
            patch("app.services.browser.browser_pool") as mock_bp,
        ):
            # DB fails
            mock_engine.connect.side_effect = Exception("Connection refused")
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis down"))
            mock_bp._initialized = False

            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "not ready"
