"""Integration tests for /v1/batch endpoints."""

import uuid

import pytest
from unittest.mock import MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_result import JobResult


# ---------------------------------------------------------------------------
# POST /v1/batch/scrape
# ---------------------------------------------------------------------------


class TestBatchScrape:
    @pytest.mark.asyncio
    async def test_batch_scrape_returns_job(self, client: AsyncClient, auth_headers):
        """POST /v1/batch/scrape creates a batch job and returns job_id."""
        with patch("app.api.v1.batch.process_batch") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post(
                "/v1/batch/scrape",
                json={
                    "urls": [
                        "https://example.com/page1",
                        "https://example.com/page2",
                        "https://example.com/page3",
                    ],
                    "formats": ["markdown"],
                    "concurrency": 3,
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "job_id" in data
            assert data["status"] == "started"
            assert data["total_urls"] == 3
            # Verify UUID format
            uuid.UUID(data["job_id"])

    @pytest.mark.asyncio
    async def test_batch_scrape_dispatches_task(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/batch/scrape dispatches a Celery task."""
        with patch("app.api.v1.batch.process_batch") as mock_task:
            mock_task.delay = MagicMock()

            await client.post(
                "/v1/batch/scrape",
                json={
                    "urls": ["https://a.com", "https://b.com"],
                },
                headers=auth_headers,
            )

            mock_task.delay.assert_called_once()
            args = mock_task.delay.call_args[0]
            assert isinstance(args[0], str)  # job_id string
            assert "urls" in args[1]

    @pytest.mark.asyncio
    async def test_batch_scrape_unauthenticated(self, client: AsyncClient):
        """POST /v1/batch/scrape without auth returns 401."""
        resp = await client.post(
            "/v1/batch/scrape",
            json={
                "urls": ["https://example.com"],
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_scrape_empty_urls(self, client: AsyncClient, auth_headers):
        """POST /v1/batch/scrape with empty URL list returns 400."""
        with patch("app.api.v1.batch.process_batch") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post(
                "/v1/batch/scrape",
                json={
                    "urls": [],
                },
                headers=auth_headers,
            )

            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_scrape_with_items(self, client: AsyncClient, auth_headers):
        """POST /v1/batch/scrape accepts items with per-URL overrides."""
        with patch("app.api.v1.batch.process_batch") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post(
                "/v1/batch/scrape",
                json={
                    "items": [
                        {"url": "https://a.com", "formats": ["markdown", "html"]},
                        {"url": "https://b.com", "timeout": 60000},
                    ],
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["total_urls"] == 2

    @pytest.mark.asyncio
    async def test_batch_scrape_message_includes_count(
        self, client: AsyncClient, auth_headers
    ):
        """The response message mentions the number of URLs."""
        with patch("app.api.v1.batch.process_batch") as mock_task:
            mock_task.delay = MagicMock()

            resp = await client.post(
                "/v1/batch/scrape",
                json={
                    "urls": ["https://a.com", "https://b.com", "https://c.com"],
                },
                headers=auth_headers,
            )

            data = resp.json()
            assert "3" in data["message"]


# ---------------------------------------------------------------------------
# GET /v1/batch/{job_id} — batch status
# ---------------------------------------------------------------------------


class TestBatchStatus:
    @pytest.mark.asyncio
    async def test_get_batch_status(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """GET /v1/batch/{id} returns batch job status with results."""
        job = Job(
            id=uuid.uuid4(),
            user_id=test_user.id,
            type="batch",
            status="completed",
            config={"urls": ["https://a.com", "https://b.com"]},
            total_pages=2,
            completed_pages=2,
        )
        db_session.add(job)
        await db_session.flush()

        for url in ["https://a.com", "https://b.com"]:
            result = JobResult(
                id=uuid.uuid4(),
                job_id=job.id,
                url=url,
                markdown=f"# Content from {url}",
                metadata_={
                    "title": f"Page: {url}",
                    "status_code": 200,
                    "source_url": url,
                    "word_count": 3,
                    "reading_time_seconds": 1,
                    "content_length": 50,
                },
            )
            db_session.add(result)
        await db_session.flush()

        resp = await client.get(f"/v1/batch/{job.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["total_urls"] == 2
        assert data["completed_urls"] == 2
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_batch_status_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/batch/{id} for a non-existent job returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/v1/batch/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_status_wrong_type(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user
    ):
        """GET /v1/batch/{id} for a non-batch job returns 404."""
        job = Job(
            id=uuid.uuid4(),
            user_id=test_user.id,
            type="crawl",  # not batch
            status="completed",
            config={"url": "https://example.com"},
        )
        db_session.add(job)
        await db_session.flush()

        resp = await client.get(f"/v1/batch/{job.id}", headers=auth_headers)
        assert resp.status_code == 404
