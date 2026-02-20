"""Integration tests for /v1/schedules endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_schedule_in_db(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str = "Daily scrape",
    cron: str = "0 6 * * *",
    schedule_type: str = "scrape",
    is_active: bool = True,
) -> Schedule:
    """Insert a schedule directly into the DB and return the ORM object."""
    now = datetime.now(timezone.utc)
    sched = Schedule(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        schedule_type=schedule_type,
        config={"url": "https://example.com"},
        cron_expression=cron,
        timezone="UTC",
        is_active=is_active,
        next_run_at=now,
        run_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(sched)
    await db.flush()
    return sched


# ---------------------------------------------------------------------------
# POST /v1/schedules — create schedule
# ---------------------------------------------------------------------------


class TestCreateSchedule:
    @pytest.mark.asyncio
    async def test_create_schedule(self, client: AsyncClient, auth_headers):
        """POST /v1/schedules creates a new schedule."""
        resp = await client.post(
            "/v1/schedules",
            json={
                "name": "Hourly scrape",
                "schedule_type": "scrape",
                "config": {"url": "https://example.com"},
                "cron_expression": "0 * * * *",
                "timezone": "UTC",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Hourly scrape"
        assert data["schedule_type"] == "scrape"
        assert data["cron_expression"] == "0 * * * *"
        assert data["is_active"] is True
        assert "id" in data
        assert "next_run_at" in data
        uuid.UUID(data["id"])  # validate UUID format

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/schedules with invalid cron returns 422."""
        resp = await client.post(
            "/v1/schedules",
            json={
                "name": "Bad cron",
                "schedule_type": "scrape",
                "config": {"url": "https://example.com"},
                "cron_expression": "not a cron",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_type(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/schedules with invalid schedule_type returns 422."""
        resp = await client.post(
            "/v1/schedules",
            json={
                "name": "Bad type",
                "schedule_type": "invalid_type",
                "config": {"url": "https://example.com"},
                "cron_expression": "0 * * * *",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_schedule_with_webhook(
        self, client: AsyncClient, auth_headers
    ):
        """Schedule can include a webhook_url."""
        resp = await client.post(
            "/v1/schedules",
            json={
                "name": "With webhook",
                "schedule_type": "crawl",
                "config": {"url": "https://example.com"},
                "cron_expression": "0 0 * * *",
                "webhook_url": "https://hooks.example.com/notify",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["webhook_url"] == "https://hooks.example.com/notify"

    @pytest.mark.asyncio
    async def test_create_schedule_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/v1/schedules",
            json={
                "name": "Unauthed",
                "schedule_type": "scrape",
                "config": {},
                "cron_expression": "0 * * * *",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/schedules — list schedules
# ---------------------------------------------------------------------------


class TestListSchedules:
    @pytest.mark.asyncio
    async def test_list_schedules(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """GET /v1/schedules returns the user's schedules."""
        await _create_schedule_in_db(db_session, test_user.id, name="Sched A")
        await _create_schedule_in_db(db_session, test_user.id, name="Sched B")

        resp = await client.get("/v1/schedules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["schedules"]) == 2
        names = {s["name"] for s in data["schedules"]}
        assert "Sched A" in names
        assert "Sched B" in names

    @pytest.mark.asyncio
    async def test_list_schedules_empty(self, client: AsyncClient, auth_headers):
        """A user with no schedules gets an empty list."""
        resp = await client.get("/v1/schedules", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 0
        assert data["schedules"] == []

    @pytest.mark.asyncio
    async def test_list_schedules_isolation(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """A user does not see another user's schedules."""
        other_user_id = uuid.uuid4()
        await _create_schedule_in_db(db_session, other_user_id, name="Other's sched")
        await _create_schedule_in_db(db_session, test_user.id, name="My sched")

        resp = await client.get("/v1/schedules", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["schedules"][0]["name"] == "My sched"


# ---------------------------------------------------------------------------
# PUT /v1/schedules/{id} — update schedule
# ---------------------------------------------------------------------------


class TestUpdateSchedule:
    @pytest.mark.asyncio
    async def test_update_schedule_name(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """PUT /v1/schedules/{id} updates the schedule name."""
        sched = await _create_schedule_in_db(db_session, test_user.id, name="Old Name")

        resp = await client.put(
            f"/v1/schedules/{sched.id}",
            json={
                "name": "New Name",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_schedule_cron(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """Updating cron_expression recalculates next_run_at."""
        sched = await _create_schedule_in_db(db_session, test_user.id, cron="0 6 * * *")

        resp = await client.put(
            f"/v1/schedules/{sched.id}",
            json={
                "cron_expression": "0 12 * * *",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cron_expression"] == "0 12 * * *"
        # next_run_at should be updated
        assert data["next_run_at"] is not None

    @pytest.mark.asyncio
    async def test_update_schedule_deactivate(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """Setting is_active=false deactivates the schedule."""
        sched = await _create_schedule_in_db(db_session, test_user.id)

        resp = await client.put(
            f"/v1/schedules/{sched.id}",
            json={
                "is_active": False,
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_schedule_invalid_cron(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """Updating with an invalid cron expression returns 422."""
        sched = await _create_schedule_in_db(db_session, test_user.id)

        resp = await client.put(
            f"/v1/schedules/{sched.id}",
            json={
                "cron_expression": "invalid cron",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_nonexistent_schedule(self, client: AsyncClient, auth_headers):
        """PUT on a non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/v1/schedules/{fake_id}",
            json={
                "name": "Ghost",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_schedule(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """A user cannot update another user's schedule."""
        other_user_id = uuid.uuid4()
        sched = await _create_schedule_in_db(db_session, other_user_id, name="Not mine")

        resp = await client.put(
            f"/v1/schedules/{sched.id}",
            json={
                "name": "Hijacked",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/schedules/{id}
# ---------------------------------------------------------------------------


class TestDeleteSchedule:
    @pytest.mark.asyncio
    async def test_delete_schedule(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """DELETE /v1/schedules/{id} removes the schedule."""
        sched = await _create_schedule_in_db(db_session, test_user.id)

        resp = await client.delete(f"/v1/schedules/{sched.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify it's gone
        get_resp = await client.get(f"/v1/schedules/{sched.id}", headers=auth_headers)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_schedule(self, client: AsyncClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/v1/schedules/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_schedule(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other_user_id = uuid.uuid4()
        sched = await _create_schedule_in_db(db_session, other_user_id)

        resp = await client.delete(f"/v1/schedules/{sched.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v1/schedules/{id}/trigger — manual trigger
# ---------------------------------------------------------------------------


class TestTriggerSchedule:
    @pytest.mark.asyncio
    async def test_trigger_schedule_creates_job(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """POST /v1/schedules/{id}/trigger creates a new job."""
        sched = await _create_schedule_in_db(
            db_session,
            test_user.id,
            name="Triggerable",
            schedule_type="scrape",
        )

        with (
            patch("app.api.v1.schedule.process_crawl", create=True) as mock_crawl,
            patch("app.api.v1.schedule.process_batch", create=True) as mock_batch,
            patch("app.api.v1.schedule.process_scrape", create=True) as mock_scrape,
        ):
            mock_scrape.delay = MagicMock()
            mock_crawl.delay = MagicMock()
            mock_batch.delay = MagicMock()

            # Need to patch the imports inside the function
            with (
                patch("app.workers.scrape_worker.process_scrape", mock_scrape),
                patch("app.workers.crawl_worker.process_crawl", mock_crawl),
                patch("app.workers.batch_worker.process_batch", mock_batch),
            ):
                resp = await client.post(
                    f"/v1/schedules/{sched.id}/trigger",
                    headers=auth_headers,
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "job_id" in data

    @pytest.mark.asyncio
    async def test_trigger_increments_run_count(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """Triggering a schedule increments run_count."""
        sched = await _create_schedule_in_db(
            db_session, test_user.id, schedule_type="scrape"
        )
        assert sched.run_count == 0

        with patch("app.workers.scrape_worker.process_scrape") as mock_task:
            mock_task.delay = MagicMock()

            await client.post(
                f"/v1/schedules/{sched.id}/trigger",
                headers=auth_headers,
            )

        # Refresh from DB
        await db_session.refresh(sched)
        assert sched.run_count == 1

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_schedule(
        self, client: AsyncClient, auth_headers
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/v1/schedules/{fake_id}/trigger", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_other_users_schedule(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other_user_id = uuid.uuid4()
        sched = await _create_schedule_in_db(db_session, other_user_id)

        resp = await client.post(
            f"/v1/schedules/{sched.id}/trigger", headers=auth_headers
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cron computation
# ---------------------------------------------------------------------------


class TestCronComputation:
    def test_compute_next_run_valid_cron(self):
        """_compute_next_run returns a future datetime for a valid cron."""
        from app.api.v1.schedule import _compute_next_run

        next_run = _compute_next_run("0 * * * *")  # Every hour
        now = datetime.now(timezone.utc)
        assert next_run > now

    def test_compute_next_run_daily(self):
        """A daily cron returns a time within the next 24 hours."""
        from app.api.v1.schedule import _compute_next_run

        next_run = _compute_next_run("0 6 * * *")  # Daily at 6 AM
        now = datetime.now(timezone.utc)
        delta = next_run - now
        assert delta.total_seconds() > 0
        assert delta.total_seconds() <= 86400  # Within 24 hours

    def test_compute_next_run_every_5_minutes(self):
        """A */5 cron returns a time within the next 5 minutes."""
        from app.api.v1.schedule import _compute_next_run

        next_run = _compute_next_run("*/5 * * * *")
        now = datetime.now(timezone.utc)
        delta = next_run - now
        assert delta.total_seconds() > 0
        assert delta.total_seconds() <= 300

    def test_human_readable_next_seconds(self):
        """_human_readable_next formats seconds correctly."""
        from app.api.v1.schedule import _human_readable_next

        future = datetime.now(timezone.utc)
        from datetime import timedelta

        future += timedelta(seconds=30)
        result = _human_readable_next(future)
        assert result.startswith("in ") and result.endswith("s")

    def test_human_readable_next_minutes(self):
        from app.api.v1.schedule import _human_readable_next
        from datetime import timedelta

        future = datetime.now(timezone.utc) + timedelta(minutes=15)
        result = _human_readable_next(future)
        assert "m" in result

    def test_human_readable_next_hours(self):
        from app.api.v1.schedule import _human_readable_next
        from datetime import timedelta

        future = datetime.now(timezone.utc) + timedelta(hours=3)
        result = _human_readable_next(future)
        assert "h" in result

    def test_human_readable_next_days(self):
        from app.api.v1.schedule import _human_readable_next
        from datetime import timedelta

        future = datetime.now(timezone.utc) + timedelta(days=5)
        result = _human_readable_next(future)
        assert "d" in result

    def test_human_readable_next_overdue(self):
        from app.api.v1.schedule import _human_readable_next
        from datetime import timedelta

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        result = _human_readable_next(past)
        assert result == "overdue"

    def test_human_readable_none(self):
        from app.api.v1.schedule import _human_readable_next

        assert _human_readable_next(None) is None
