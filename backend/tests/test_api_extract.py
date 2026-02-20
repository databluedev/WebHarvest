"""Integration tests for /v1/extract endpoints."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient


class TestExtractWithContent:
    @pytest.mark.asyncio
    async def test_extract_with_content_success(
        self, client: AsyncClient, auth_headers
    ):
        """POST /v1/extract with direct content returns extracted data."""
        with (
            patch(
                "app.api.v1.extract.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.extract.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.extract.increment_usage", new_callable=AsyncMock),
            patch(
                "app.api.v1.extract.extract_with_llm", new_callable=AsyncMock
            ) as mock_extract,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=100, remaining=99, reset=60
            )
            mock_extract.return_value = {
                "name": "John Doe",
                "email": "john@example.com",
            }

            resp = await client.post(
                "/v1/extract",
                json={
                    "content": "# About\nJohn Doe - john@example.com",
                    "prompt": "Extract the name and email",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["extract"]["name"] == "John Doe"
            assert data["data"]["content_length"] > 0

    @pytest.mark.asyncio
    async def test_extract_with_html(self, client: AsyncClient, auth_headers):
        """POST /v1/extract with HTML content extracts data."""
        with (
            patch(
                "app.api.v1.extract.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.extract.check_quota", new_callable=AsyncMock),
            patch("app.api.v1.extract.increment_usage", new_callable=AsyncMock),
            patch(
                "app.api.v1.extract.extract_with_llm", new_callable=AsyncMock
            ) as mock_extract,
            patch(
                "app.api.v1.extract.html_to_markdown",
                return_value="Product: Widget $9.99",
            ),
            patch(
                "app.api.v1.extract.extract_main_content",
                return_value="<p>Product: Widget $9.99</p>",
            ),
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=100, remaining=99, reset=60
            )
            mock_extract.return_value = {"product": "Widget", "price": "$9.99"}

            resp = await client.post(
                "/v1/extract",
                json={
                    "html": "<html><body><p>Product: Widget $9.99</p></body></html>",
                    "prompt": "Extract product info",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True


class TestExtractValidation:
    @pytest.mark.asyncio
    async def test_extract_no_content_or_url(self, client: AsyncClient, auth_headers):
        """POST /v1/extract without content/url returns 400."""
        with patch(
            "app.api.v1.extract.check_rate_limit_full", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.return_value = MagicMock(
                allowed=True, limit=100, remaining=99, reset=60
            )

            resp = await client.post(
                "/v1/extract",
                json={
                    "prompt": "Extract something",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_extract_no_prompt_or_schema(self, client: AsyncClient, auth_headers):
        """POST /v1/extract without prompt or schema returns 400."""
        with patch(
            "app.api.v1.extract.check_rate_limit_full", new_callable=AsyncMock
        ) as mock_rl:
            mock_rl.return_value = MagicMock(
                allowed=True, limit=100, remaining=99, reset=60
            )

            resp = await client.post(
                "/v1/extract",
                json={
                    "content": "Some text content",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_extract_unauthenticated(self, client: AsyncClient):
        """POST /v1/extract without auth returns 401."""
        resp = await client.post(
            "/v1/extract",
            json={
                "content": "test",
                "prompt": "test",
            },
        )
        assert resp.status_code == 401


class TestExtractLLMError:
    @pytest.mark.asyncio
    async def test_extract_llm_failure(self, client: AsyncClient, auth_headers):
        """POST /v1/extract when LLM fails returns success=false."""
        with (
            patch(
                "app.api.v1.extract.check_rate_limit_full", new_callable=AsyncMock
            ) as mock_rl,
            patch("app.api.v1.extract.check_quota", new_callable=AsyncMock),
            patch(
                "app.api.v1.extract.extract_with_llm", new_callable=AsyncMock
            ) as mock_extract,
        ):
            mock_rl.return_value = MagicMock(
                allowed=True, limit=100, remaining=99, reset=60
            )
            mock_extract.side_effect = RuntimeError("LLM API error")

            resp = await client.post(
                "/v1/extract",
                json={
                    "content": "Some content",
                    "prompt": "Extract data",
                },
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "LLM API error" in data["error"]


class TestGetExtractStatus:
    @pytest.mark.asyncio
    async def test_get_extract_not_found(self, client: AsyncClient, auth_headers):
        """GET /v1/extract/{id} with invalid job returns 404."""
        resp = await client.get(f"/v1/extract/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_extract_unauthenticated(self, client: AsyncClient):
        """GET /v1/extract/{id} without auth returns 401."""
        resp = await client.get(f"/v1/extract/{uuid.uuid4()}")
        assert resp.status_code == 401
