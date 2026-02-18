"""Unit tests for app.services.webhook — delivery, HMAC signing, retries."""

import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.services.webhook import send_webhook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_expected_signature(payload: dict, secret: str) -> str:
    """Compute the expected HMAC-SHA256 signature for a payload."""
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# Successful delivery
# ---------------------------------------------------------------------------


class TestWebhookSuccess:

    @pytest.mark.asyncio
    async def test_successful_delivery_returns_true(self):
        """A 200 response on the first attempt returns True."""
        mock_response = httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "crawl.completed", "job_id": "abc123"},
            )
            assert result is True
            instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_2xx_range_succeeds(self):
        """Any status < 400 is considered success."""
        mock_response = httpx.Response(201, request=httpx.Request("POST", "https://hook.example.com"))

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "test"},
            )
            assert result is True


# ---------------------------------------------------------------------------
# HMAC-SHA256 signature
# ---------------------------------------------------------------------------


class TestWebhookHMAC:

    @pytest.mark.asyncio
    async def test_hmac_signature_header_present(self):
        """When a secret is provided, X-WebHarvest-Signature is set."""
        mock_response = httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return mock_response

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            payload = {"event": "crawl.completed", "data": {"pages": 10}}
            secret = "my-webhook-secret"
            await send_webhook(url="https://hook.example.com", payload=payload, secret=secret)

            assert "X-WebHarvest-Signature" in captured_headers
            expected = _compute_expected_signature(payload, secret)
            assert captured_headers["X-WebHarvest-Signature"] == expected

    @pytest.mark.asyncio
    async def test_no_signature_without_secret(self):
        """When no secret is provided, the signature header is absent."""
        mock_response = httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return mock_response

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await send_webhook(url="https://hook.example.com", payload={"event": "test"})
            assert "X-WebHarvest-Signature" not in captured_headers

    @pytest.mark.asyncio
    async def test_signature_matches_body_bytes(self):
        """The signature is computed over the exact JSON body bytes sent."""
        mock_response = httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))
        captured_body = None
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                nonlocal captured_body
                captured_body = content
                captured_headers.update(headers)
                return mock_response

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            secret = "verify-me"
            payload = {"event": "scrape.done", "url": "https://example.com"}
            await send_webhook(url="https://hook.example.com", payload=payload, secret=secret)

            # Recompute from captured body bytes
            expected_sig = hmac.new(
                secret.encode("utf-8"), captured_body, hashlib.sha256
            ).hexdigest()
            assert captured_headers["X-WebHarvest-Signature"] == f"sha256={expected_sig}"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestWebhookRetry:

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self):
        """Retries up to max_retries on 500 errors, returns False."""
        error_response = httpx.Response(500, request=httpx.Request("POST", "https://hook.example.com"))
        call_count = 0

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient, \
             patch("app.services.webhook.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            instance = AsyncMock()

            async def _failing_post(url, content, headers):
                nonlocal call_count
                call_count += 1
                return error_response

            instance.post = _failing_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "fail"},
                max_retries=3,
            )
            assert result is False
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_exception(self):
        """Network exceptions trigger retries."""
        call_count = 0

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient, \
             patch("app.services.webhook.asyncio.sleep", new_callable=AsyncMock):
            instance = AsyncMock()

            async def _exception_post(url, content, headers):
                nonlocal call_count
                call_count += 1
                raise httpx.ConnectError("Connection refused")

            instance.post = _exception_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "fail"},
                max_retries=3,
            )
            assert result is False
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failure(self):
        """If the second attempt succeeds, returns True."""
        ok_response = httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))
        error_response = httpx.Response(502, request=httpx.Request("POST", "https://hook.example.com"))
        call_count = 0

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient, \
             patch("app.services.webhook.asyncio.sleep", new_callable=AsyncMock):
            instance = AsyncMock()

            async def _transient_post(url, content, headers):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return error_response
                return ok_response

            instance.post = _transient_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "retry-test"},
                max_retries=3,
            )
            assert result is True
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Backoff delays follow the pattern: 1s, 4s (base * 4^attempt)."""
        error_response = httpx.Response(500, request=httpx.Request("POST", "https://hook.example.com"))
        sleep_calls = []

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient, \
             patch("app.services.webhook.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

            async def _record_sleep(delay):
                sleep_calls.append(delay)

            mock_sleep.side_effect = _record_sleep

            instance = AsyncMock()
            instance.post = AsyncMock(return_value=error_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await send_webhook(
                url="https://hook.example.com",
                payload={"event": "backoff-test"},
                max_retries=3,
            )

            # After attempt 0 -> sleep 1s, after attempt 1 -> sleep 4s, no sleep after last attempt
            assert len(sleep_calls) == 2
            assert sleep_calls[0] == 1    # 1 * 4^0
            assert sleep_calls[1] == 4    # 1 * 4^1


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


class TestWebhookTimeout:

    @pytest.mark.asyncio
    async def test_timeout_is_passed_to_client(self):
        """The timeout parameter is forwarded to httpx.AsyncClient."""
        captured_timeout = None

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post = AsyncMock(
                return_value=httpx.Response(200, request=httpx.Request("POST", "https://hook.example.com"))
            )
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)

            def _capture_init(*args, **kwargs):
                nonlocal captured_timeout
                captured_timeout = kwargs.get("timeout")
                return instance

            MockClient.side_effect = _capture_init

            await send_webhook(
                url="https://hook.example.com",
                payload={"event": "test"},
                timeout=5.0,
            )
            assert captured_timeout == 5.0

    @pytest.mark.asyncio
    async def test_timeout_exception_triggers_retry(self):
        """httpx.TimeoutException is caught and retried."""
        call_count = 0

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient, \
             patch("app.services.webhook.asyncio.sleep", new_callable=AsyncMock):
            instance = AsyncMock()

            async def _timeout_post(url, content, headers):
                nonlocal call_count
                call_count += 1
                raise httpx.TimeoutException("Request timed out")

            instance.post = _timeout_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await send_webhook(
                url="https://hook.example.com",
                payload={"event": "timeout-test"},
                max_retries=2,
                timeout=1.0,
            )
            assert result is False
            assert call_count == 2


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------


class TestWebhookPayload:

    @pytest.mark.asyncio
    async def test_payload_sent_as_json_bytes(self):
        """The payload is serialized as JSON and sent as bytes."""
        captured_body = None

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                nonlocal captured_body
                captured_body = content
                return httpx.Response(200, request=httpx.Request("POST", url))

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            payload = {"event": "crawl.completed", "job_id": "abc", "pages": 42}
            await send_webhook(url="https://hook.example.com", payload=payload)

            decoded = json.loads(captured_body)
            assert decoded["event"] == "crawl.completed"
            assert decoded["job_id"] == "abc"
            assert decoded["pages"] == 42

    @pytest.mark.asyncio
    async def test_event_header_set_from_payload(self):
        """X-WebHarvest-Event header is set to the event name from payload."""
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return httpx.Response(200, request=httpx.Request("POST", url))

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await send_webhook(
                url="https://hook.example.com",
                payload={"event": "batch.done"},
            )
            assert captured_headers["X-WebHarvest-Event"] == "batch.done"

    @pytest.mark.asyncio
    async def test_user_agent_header(self):
        """User-Agent is set to WebHarvest-Webhook/1.0."""
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return httpx.Response(200, request=httpx.Request("POST", url))

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await send_webhook(url="https://hook.example.com", payload={"event": "test"})
            assert captured_headers["User-Agent"] == "WebHarvest-Webhook/1.0"

    @pytest.mark.asyncio
    async def test_delivery_timestamp_header(self):
        """X-WebHarvest-Delivery header contains a Unix timestamp."""
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return httpx.Response(200, request=httpx.Request("POST", url))

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            before = int(time.time())
            await send_webhook(url="https://hook.example.com", payload={"event": "test"})
            after = int(time.time())

            delivery_ts = int(captured_headers["X-WebHarvest-Delivery"])
            assert before <= delivery_ts <= after

    @pytest.mark.asyncio
    async def test_content_type_is_json(self):
        """Content-Type header is application/json."""
        captured_headers = {}

        with patch("app.services.webhook.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()

            async def _capture_post(url, content, headers):
                captured_headers.update(headers)
                return httpx.Response(200, request=httpx.Request("POST", url))

            instance.post = _capture_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await send_webhook(url="https://hook.example.com", payload={"event": "test"})
            assert captured_headers["Content-Type"] == "application/json"
