"""Integration tests for /v1/monitors endpoints."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient


class TestCreateMonitor:
    @pytest.mark.asyncio
    async def test_create_monitor_success(self, client: AsyncClient, auth_headers):
        """POST /v1/monitors creates a monitor and returns it."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "Example Monitor",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["monitor"]["name"] == "Example Monitor"
            assert data["monitor"]["url"] == "https://example.com"
            assert data["monitor"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_monitor_unauthenticated(self, client: AsyncClient):
        """POST /v1/monitors without auth returns 401."""
        resp = await client.post(
            "/v1/monitors",
            json={
                "name": "Test",
                "url": "https://example.com",
                "check_interval_minutes": 60,
                "notify_on": "any_change",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_monitor_invalid_interval(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/monitors with interval < 5 returns 400."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )

            resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "Test",
                    "url": "https://example.com",
                    "check_interval_minutes": 2,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_monitor_invalid_notify_on(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/monitors with invalid notify_on returns 400."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )

            resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "Test",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "invalid_type",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 400


class TestListMonitors:
    @pytest.mark.asyncio
    async def test_list_monitors_empty(self, client: AsyncClient, auth_headers):
        """GET /v1/monitors returns empty list when no monitors exist."""
        resp = await client.get("/v1/monitors", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["monitors"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_monitors_unauthenticated(self, client: AsyncClient):
        """GET /v1/monitors without auth returns 401."""
        resp = await client.get("/v1/monitors")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_monitors_after_create(self, client: AsyncClient, auth_headers):
        """GET /v1/monitors returns created monitors."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            await client.post(
                "/v1/monitors",
                json={
                    "name": "My Monitor",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

        resp = await client.get("/v1/monitors", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["monitors"][0]["name"] == "My Monitor"


class TestGetMonitor:
    @pytest.mark.asyncio
    async def test_get_monitor_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/monitors/{id} with invalid ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/v1/monitors/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateMonitor:
    @pytest.mark.asyncio
    async def test_update_monitor(self, client: AsyncClient, auth_headers):
        """PATCH /v1/monitors/{id} updates monitor fields."""
        # Create a monitor first
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            create_resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "Original Name",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

        monitor_id = create_resp.json()["monitor"]["id"]

        resp = await client.patch(
            f"/v1/monitors/{monitor_id}",
            json={
                "name": "Updated Name",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["monitor"]["name"] == "Updated Name"


class TestDeleteMonitor:
    @pytest.mark.asyncio
    async def test_delete_monitor(self, client: AsyncClient, auth_headers):
        """DELETE /v1/monitors/{id} removes the monitor."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            create_resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "To Delete",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

        monitor_id = create_resp.json()["monitor"]["id"]

        resp = await client.delete(f"/v1/monitors/{monitor_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it's gone
        resp = await client.get(f"/v1/monitors/{monitor_id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_monitor_not_found(self, client: AsyncClient, auth_headers):
        """DELETE /v1/monitors/{id} for non-existent monitor returns 404."""
        resp = await client.delete(f"/v1/monitors/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


class TestTriggerCheck:
    @pytest.mark.asyncio
    async def test_trigger_check(self, client: AsyncClient, auth_headers):
        """POST /v1/monitors/{id}/check queues a check task."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            create_resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "Check Me",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

        monitor_id = create_resp.json()["monitor"]["id"]

        with patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post(
                f"/v1/monitors/{monitor_id}/check", headers=auth_headers
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            mock_task.delay.assert_called_once_with(monitor_id)


class TestMonitorHistory:
    @pytest.mark.asyncio
    async def test_history_empty(self, client: AsyncClient, auth_headers):
        """GET /v1/monitors/{id}/history returns empty when no checks exist."""
        with (
            patch(
                "app.api.v1.monitor.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.monitor.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.monitor.increment_usage", new_callable=AsyncMock),
            patch("app.workers.monitor_worker.check_single_monitor_task") as mock_task,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=30, remaining=29, reset=60
            )
            mock_task.delay = MagicMock()

            create_resp = await client.post(
                "/v1/monitors",
                json={
                    "name": "History Test",
                    "url": "https://example.com",
                    "check_interval_minutes": 60,
                    "notify_on": "any_change",
                },
                headers=auth_headers,
            )

        monitor_id = create_resp.json()["monitor"]["id"]

        resp = await client.get(
            f"/v1/monitors/{monitor_id}/history", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["checks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_history_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/monitors/{id}/history for non-existent monitor returns 404."""
        resp = await client.get(
            f"/v1/monitors/{uuid.uuid4()}/history", headers=auth_headers
        )
        assert resp.status_code == 404
