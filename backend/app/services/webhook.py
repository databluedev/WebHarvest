"""Webhook delivery service with HMAC signing and retries."""

import hashlib
import hmac
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)


async def send_webhook(
    url: str,
    payload: dict,
    secret: str | None = None,
    max_retries: int = 3,
    timeout: float = 10.0,
) -> bool:
    """POST JSON payload to a webhook URL with optional HMAC-SHA256 signing.

    Args:
        url: The webhook endpoint URL.
        payload: JSON-serializable dict to send.
        secret: Optional secret for HMAC-SHA256 signature.
        max_retries: Number of retries on failure (default 3).
        timeout: Request timeout in seconds (default 10).

    Returns:
        True if delivery succeeded, False otherwise.
    """
    body = json.dumps(payload, default=str, ensure_ascii=False)
    body_bytes = body.encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "WebHarvest-Webhook/1.0",
        "X-WebHarvest-Event": payload.get("event", "unknown"),
        "X-WebHarvest-Delivery": str(int(time.time())),
    }

    # HMAC-SHA256 signature
    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers["X-WebHarvest-Signature"] = f"sha256={signature}"

    # Retry with exponential backoff: 1s, 4s, 16s
    backoff_base = 1
    last_error = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(url, content=body_bytes, headers=headers)
                if response.status_code < 400:
                    logger.info(
                        f"Webhook delivered to {url}: {response.status_code} "
                        f"(attempt {attempt + 1})"
                    )
                    return True

                logger.warning(
                    f"Webhook to {url} returned {response.status_code} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                last_error = f"HTTP {response.status_code}"

            except Exception as e:
                logger.warning(
                    f"Webhook to {url} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                last_error = str(e)

            # Exponential backoff before next retry
            if attempt < max_retries - 1:
                import asyncio
                delay = backoff_base * (4 ** attempt)  # 1s, 4s, 16s
                await asyncio.sleep(delay)

    logger.error(f"Webhook to {url} failed after {max_retries} attempts: {last_error}")
    return False
