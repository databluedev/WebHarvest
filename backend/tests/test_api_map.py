"""Integration tests for /v1/map endpoints."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient


class TestMapSite:
    @pytest.mark.asyncio
    async def test_map_site_success(self, client: AsyncClient, auth_headers):
        """POST /v1/map dispatches to Celery and returns a job_id."""
        with patch(
            "app.api.v1.map.process_map"
        ) as mock_task:
            mock_task.delay = MagicMock()

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
            assert "job_id" in data
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_site_unauthenticated(self, client: AsyncClient):
        """POST /v1/map without auth returns 401."""
        resp = await client.post("/v1/map", json={"url": "https://example.com"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_map_site_missing_url(self, client: AsyncClient, auth_headers):
        """POST /v1/map without url field returns 422."""
        resp = await client.post("/v1/map", json={}, headers=auth_headers)
        assert resp.status_code == 422


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
