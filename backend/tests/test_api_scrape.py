"""Integration tests for POST /v1/scrape."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.schemas.scrape import ScrapeData, PageMetadata


# ---------------------------------------------------------------------------
# POST /v1/scrape
# ---------------------------------------------------------------------------


class TestScrapeEndpoint:

    @pytest.mark.asyncio
    async def test_scrape_success(self, client: AsyncClient, auth_headers):
        """POST /v1/scrape with a mocked scraper returns the expected schema."""
        mock_scrape_data = ScrapeData(
            markdown="# Hello World\n\nThis is the scraped content.",
            html="<h1>Hello World</h1><p>This is the scraped content.</p>",
            links=["https://example.com/link1", "https://example.com/link2"],
            metadata=PageMetadata(
                title="Hello World",
                description="A test page",
                language="en",
                source_url="https://example.com",
                status_code=200,
                word_count=7,
                reading_time_seconds=2,
                content_length=1024,
            ),
        )

        with patch("app.api.v1.scrape.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_scrape_data

            resp = await client.post("/v1/scrape", json={
                "url": "https://example.com",
                "formats": ["markdown", "html", "links"],
            }, headers=auth_headers)

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["markdown"] is not None
            assert "Hello World" in data["data"]["markdown"]
            assert data["data"]["metadata"]["title"] == "Hello World"
            assert data["data"]["metadata"]["status_code"] == 200
            assert isinstance(data["data"]["links"], list)

    @pytest.mark.asyncio
    async def test_scrape_unauthenticated(self, client: AsyncClient):
        """POST /v1/scrape without auth returns 401."""
        resp = await client.post("/v1/scrape", json={
            "url": "https://example.com",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_scrape_missing_url(self, client: AsyncClient, auth_headers):
        """POST /v1/scrape without url field returns 422."""
        resp = await client.post("/v1/scrape", json={
            "formats": ["markdown"],
        }, headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_scrape_error_returns_success_false(self, client: AsyncClient, auth_headers):
        """When the scraper raises, the response has success=false and an error message."""
        with patch("app.api.v1.scrape.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.side_effect = RuntimeError("Browser crashed")

            resp = await client.post("/v1/scrape", json={
                "url": "https://example.com",
            }, headers=auth_headers)

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "Browser crashed" in data["error"]

    @pytest.mark.asyncio
    async def test_scrape_response_schema_fields(self, client: AsyncClient, auth_headers):
        """Verify the full shape of a successful scrape response."""
        mock_scrape_data = ScrapeData(
            markdown="Content",
            metadata=PageMetadata(
                source_url="https://example.com",
                status_code=200,
            ),
        )

        with patch("app.api.v1.scrape.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_scrape_data

            resp = await client.post("/v1/scrape", json={
                "url": "https://example.com",
            }, headers=auth_headers)

            data = resp.json()
            # Top-level keys
            assert "success" in data
            assert "data" in data
            # Data keys
            assert "markdown" in data["data"]
            assert "metadata" in data["data"]
            assert "source_url" in data["data"]["metadata"]
            assert "status_code" in data["data"]["metadata"]
