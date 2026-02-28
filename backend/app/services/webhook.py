"""Webhook delivery service with retries and delivery logging."""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


async def send_webhook(
    url: str,
    payload: dict,
    secret: str | None = None,
    max_retries: int = 3,
    timeout: float = 10.0,
    user_id: str | None = None,
    job_id: str | None = None,
) -> bool:
    """POST JSON payload to a webhook URL.

    Args:
        url: The webhook endpoint URL.
        payload: JSON-serializable dict to send.
        secret: HMAC-SHA256 secret for signing the payload.
        max_retries: Number of retries on failure (default 3).
        timeout: Request timeout in seconds (default 10).
        user_id: Optional user ID for delivery logging.
        job_id: Optional job ID for delivery logging.

    Returns:
        True if delivery succeeded, False otherwise.
    """
    body = json.dumps(payload, default=str, ensure_ascii=False)
    body_bytes = body.encode("utf-8")
    event = payload.get("event", "unknown")
    delivery_ts = str(int(time.time()))

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DataBlue-Webhook/1.0",
        "X-DataBlue-Event": event,
        "X-DataBlue-Delivery": delivery_ts,
    }

    # HMAC-SHA256 signature when secret is provided
    if secret:
        signature = hmac.new(
            secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        headers["X-DataBlue-Signature"] = f"sha256={signature}"

    # Retry with exponential backoff: 1s, 4s, 16s
    last_error = None
    success = False

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            start_ms = int(time.time() * 1000)
            status_code = None
            response_body = None
            response_headers_dict = None
            error_msg = None

            try:
                response = await client.post(url, content=body_bytes, headers=headers)
                status_code = response.status_code
                response_body = response.text[:2000]  # Truncate large responses
                response_headers_dict = dict(response.headers)

                if response.status_code < 400:
                    logger.info(
                        f"Webhook delivered to {url}: {response.status_code} "
                        f"(attempt {attempt + 1})"
                    )
                    success = True
                else:
                    logger.warning(
                        f"Webhook to {url} returned {response.status_code} "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    last_error = f"HTTP {response.status_code}"
                    error_msg = last_error

            except Exception as e:
                logger.warning(
                    f"Webhook to {url} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                last_error = str(e)
                error_msg = last_error

            elapsed_ms = int(time.time() * 1000) - start_ms

            # Log delivery attempt
            if user_id:
                try:
                    await _log_delivery(
                        user_id=user_id,
                        job_id=job_id,
                        url=url,
                        event=event,
                        payload=payload,
                        request_headers=headers,
                        status_code=status_code,
                        response_body=response_body,
                        response_headers=response_headers_dict,
                        response_time_ms=elapsed_ms,
                        success=success,
                        attempt=attempt + 1,
                        max_attempts=max_retries,
                        error=error_msg,
                        next_retry_at=(
                            datetime.now(timezone.utc) + timedelta(seconds=4**attempt)
                            if not success and attempt < max_retries - 1
                            else None
                        ),
                    )
                except Exception as log_err:
                    logger.debug(f"Failed to log webhook delivery: {log_err}")

            if success:
                return True

            # Exponential backoff before next retry
            if attempt < max_retries - 1:
                delay = 1 * (4**attempt)  # 1s, 4s, 16s
                await asyncio.sleep(delay)

    logger.error(f"Webhook to {url} failed after {max_retries} attempts: {last_error}")
    return False


async def send_webhook_test(url: str, secret: str | None = None) -> dict:
    """Send a test webhook to verify endpoint connectivity.

    Returns dict with status, response details, and timing.
    """
    payload = {
        "event": "webhook.test",
        "message": "This is a test webhook from DataBlue",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    body = json.dumps(payload, default=str, ensure_ascii=False)
    body_bytes = body.encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DataBlue-Webhook/1.0",
        "X-DataBlue-Event": "webhook.test",
        "X-DataBlue-Delivery": str(int(time.time())),
    }

    if secret:
        signature = hmac.new(
            secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        headers["X-DataBlue-Signature"] = f"sha256={signature}"

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, content=body_bytes, headers=headers)
            elapsed_ms = int((time.time() - start) * 1000)
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "response_body": response.text[:2000],
                "response_time_ms": elapsed_ms,
                "headers_sent": headers,
            }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "error": str(e),
            "response_time_ms": elapsed_ms,
            "headers_sent": headers,
        }


async def _log_delivery(
    user_id: str,
    job_id: str | None,
    url: str,
    event: str,
    payload: dict,
    request_headers: dict,
    status_code: int | None,
    response_body: str | None,
    response_headers: dict | None,
    response_time_ms: int,
    success: bool,
    attempt: int,
    max_attempts: int,
    error: str | None,
    next_retry_at: datetime | None,
):
    """Log a webhook delivery attempt to the database."""
    from app.core.database import create_worker_session_factory
    from app.models.webhook_delivery import WebhookDelivery

    session_factory, db_engine = create_worker_session_factory()
    try:
        async with session_factory() as db:
            delivery = WebhookDelivery(
                user_id=UUID(user_id),
                job_id=UUID(job_id) if job_id else None,
                url=url,
                event=event,
                payload=payload,
                request_headers=request_headers,
                status_code=status_code,
                response_body=response_body,
                response_headers=response_headers,
                response_time_ms=response_time_ms,
                success=success,
                attempt=attempt,
                max_attempts=max_attempts,
                error=error,
                next_retry_at=next_retry_at,
            )
            db.add(delivery)
            await db.commit()
    except Exception as e:
        logger.debug(f"Failed to persist webhook delivery log: {e}")
    finally:
        await db_engine.dispose()
