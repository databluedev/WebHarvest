"""Integration tests for /v1/crawl endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_result import JobResult


# ---------------------------------------------------------------------------
# POST /v1/crawl — start a crawl job
# ---------------------------------------------------------------------------


class TestStartCrawl:

    @pytest.mark.asyncio
    async def test_start_crawl_returns_job_id(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        """POST /v1/crawl creates a job and returns job_id."""
        with patch("app.api.v1.crawl.process_crawl") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post("/v1/crawl", json={
                "url": "https://example.com",
                "max_pages": 10,
                "max_depth": 2,
            }, headers=auth_headers)

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "job_id" in data
            assert data["status"] == "started"
            # Verify UUID format
            uuid.UUID(data["job_id"])

    @pytest.mark.asyncio
    async def test_start_crawl_unauthenticated(self, client: AsyncClient):
        """POST /v1/crawl without auth returns 401."""
        resp = await client.post("/v1/crawl", json={
            "url": "https://example.com",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_start_crawl_missing_url(self, client: AsyncClient, auth_headers):
        """POST /v1/crawl without url returns 422."""
        resp = await client.post("/v1/crawl", json={
            "max_pages": 10,
        }, headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_start_crawl_dispatches_celery_task(self, client: AsyncClient, auth_headers):
        """POST /v1/crawl calls process_crawl.delay()."""
        with patch("app.api.v1.crawl.process_crawl") as mock_task:
            mock_task.delay = MagicMock()

            await client.post("/v1/crawl", json={
                "url": "https://example.com",
                "max_pages": 5,
            }, headers=auth_headers)

            mock_task.delay.assert_called_once()
            args = mock_task.delay.call_args[0]
            assert isinstance(args[0], str)  # job_id
            assert args[1]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# GET /v1/crawl/{id} — crawl job status
# ---------------------------------------------------------------------------


class TestCrawlStatus:

    @pytest.mark.asyncio
    async def test_get_crawl_status(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user):
        """GET /v1/crawl/{id} returns the job status and results."""
        # Create a job directly in the DB
        job = Job(
            id=uuid.uuid4(),
            user_id=test_user.id,
            type="crawl",
            status="completed",
            config={"url": "https://example.com", "max_pages": 5},
            total_pages=2,
            completed_pages=2,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(job)
        await db_session.flush()

        # Add a result
        result = JobResult(
            id=uuid.uuid4(),
            job_id=job.id,
            url="https://example.com",
            markdown="# Example",
            html="<h1>Example</h1>",
            links=["https://example.com/about"],
            metadata_={
                "title": "Example",
                "status_code": 200,
                "word_count": 1,
                "source_url": "https://example.com",
                "reading_time_seconds": 0,
                "content_length": 100,
            },
        )
        db_session.add(result)
        await db_session.flush()

        resp = await client.get(f"/v1/crawl/{job.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["total_pages"] == 2
        assert data["completed_pages"] == 2
        assert data["data"] is not None
        assert len(data["data"]) == 1
        assert data["data"][0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_crawl_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/crawl/{id} with a non-existent UUID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/v1/crawl/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_crawl_other_users_job(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        """A user cannot see another user's crawl job."""
        other_user_id = uuid.uuid4()
        job = Job(
            id=uuid.uuid4(),
            user_id=other_user_id,
            type="crawl",
            status="completed",
            config={"url": "https://other.com"},
        )
        db_session.add(job)
        await db_session.flush()

        resp = await client.get(f"/v1/crawl/{job.id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_crawl_status_pending(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user):
        """A pending crawl job returns status='pending' with empty data."""
        job = Job(
            id=uuid.uuid4(),
            user_id=test_user.id,
            type="crawl",
            status="pending",
            config={"url": "https://example.com"},
            total_pages=0,
            completed_pages=0,
        )
        db_session.add(job)
        await db_session.flush()

        resp = await client.get(f"/v1/crawl/{job.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["data"] == []
