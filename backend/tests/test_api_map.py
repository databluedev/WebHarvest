"""Integration tests for /v1/map endpoints."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from app.schemas.map import LinkResult


class TestMapSite:
    @pytest.mark.asyncio
    async def test_map_site_success(self, client: AsyncClient, auth_headers):
        """POST /v1/map with mocked mapper returns discovered links."""
        mock_links = [
            LinkResult(
                url="https://example.com/page1",
                title="Page 1",
                description="First page",
            ),
            LinkResult(
                url="https://example.com/page2",
                title="Page 2",
                description="Second page",
            ),
        ]

        with (
            patch(
                "app.api.v1.map.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.map.map_website", new_callable=AsyncMock) as mock_map,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=50, remaining=49, reset=60
            )
            mock_map.return_value = mock_links

            resp = await client.post(
                "/v1/map",
                json={
                    "url": "https://example.com",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["total"] == 2
            assert len(data["links"]) == 2

    @pytest.mark.asyncio
    async def test_map_site_unauthenticated(self, client: AsyncClient):
        """POST /v1/map without auth returns 401."""
        resp = await client.post("/v1/map", json={"url": "https://example.com"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_map_site_missing_url(self, client: AsyncClient, auth_headers):
        """POST /v1/map without url field returns 422."""
        with patch(
            "app.api.v1.map.check_rate_limit_full", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.return_value = MagicMock(
                allowed=True, limit=50, remaining=49, reset=60
            )

            resp = await client.post("/v1/map", json={}, headers=auth_headers)
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_map_site_error_returns_success_false(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/map when mapper raises returns success=false."""
        with (
            patch(
                "app.api.v1.map.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.map.map_website", new_callable=AsyncMock) as mock_map,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=50, remaining=49, reset=60
            )
            mock_map.side_effect = RuntimeError("Sitemap unreachable")

            resp = await client.post(
                "/v1/map",
                json={
                    "url": "https://example.com",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "Sitemap unreachable" in data["error"]


class TestGetMapStatus:
    @pytest.mark.asyncio
    async def test_get_map_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/map/{id} with invalid job returns 404."""
        resp = await client.get(f"/v1/map/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_map_unauthenticated(self, client: AsyncClient):
        """GET /v1/map/{id} without auth returns 401."""
        resp = await client.get(f"/v1/map/{uuid.uuid4()}")
        assert resp.status_code == 401


class TestExportMap:
    @pytest.mark.asyncio
    async def test_export_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/map/{id}/export with invalid job returns 404."""
        resp = await client.get(
            f"/v1/map/{uuid.uuid4()}/export?format=json", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_unauthenticated(self, client: AsyncClient):
        """GET /v1/map/{id}/export without auth returns 401."""
        resp = await client.get(f"/v1/map/{uuid.uuid4()}/export?format=json")
        assert resp.status_code == 401
