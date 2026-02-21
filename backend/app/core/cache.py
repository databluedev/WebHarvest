import asyncio
import hashlib
import json
import logging

from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

CACHE_PREFIX = "cache:scrape:"
INFLIGHT_PREFIX = "inflight:scrape:"


def _cache_key(url: str, formats: list[str]) -> str:
    """Generate a SHA256-based cache key from URL and formats."""
    key_data = f"{url}:{','.join(sorted(formats))}"
    digest = hashlib.sha256(key_data.encode()).hexdigest()
    return f"{CACHE_PREFIX}{digest}"


async def get_cached_scrape(url: str, formats: list[str]) -> dict | None:
    """Retrieve a cached scrape result. Returns None if not cached or cache disabled."""
    if not settings.CACHE_ENABLED:
        return None

    try:
        key = _cache_key(url, formats)
        data = await redis_client.get(key)
        if data:
            logger.debug(f"Cache hit for {url}")
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    return None


async def set_cached_scrape(
    url: str, formats: list[str], data: dict, ttl: int | None = None
) -> None:
    """Store a scrape result in cache."""
    if not settings.CACHE_ENABLED:
        return

    try:
        key = _cache_key(url, formats)
        ttl = ttl or settings.CACHE_TTL_SECONDS
        await redis_client.setex(key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cached scrape for {url} (TTL={ttl}s)")
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")


def _inflight_key(url: str, formats: list[str]) -> str:
    """Generate a Redis key for the in-flight lock, reusing the same hash."""
    key_data = f"{url}:{','.join(sorted(formats))}"
    digest = hashlib.sha256(key_data.encode()).hexdigest()
    return f"{INFLIGHT_PREFIX}{digest}"


async def try_claim_inflight(url: str, formats: list[str]) -> bool:
    """Try to claim the in-flight lock for a URL+formats combo.

    Uses SETNX so only one caller wins. Returns True if this caller
    should perform the scrape; False if another request already owns it.
    """
    if not settings.CACHE_ENABLED:
        return True  # caching disabled — always scrape

    try:
        key = _inflight_key(url, formats)
        acquired = await redis_client.set(key, "1", nx=True, ex=120)
        if acquired:
            logger.debug(f"Claimed in-flight lock for {url}")
        return bool(acquired)
    except Exception as e:
        logger.warning(f"In-flight claim failed: {e}")
        return True  # on error, fall through to scrape normally


async def release_inflight(url: str, formats: list[str]) -> None:
    """Release the in-flight lock after scrape completes (success or failure)."""
    if not settings.CACHE_ENABLED:
        return

    try:
        key = _inflight_key(url, formats)
        await redis_client.delete(key)
        logger.debug(f"Released in-flight lock for {url}")
    except Exception as e:
        logger.warning(f"In-flight release failed: {e}")


async def wait_for_cached_result(
    url: str,
    formats: list[str],
    timeout: float = 90,
    poll_interval: float | None = None,
) -> dict | None:
    """Poll for a cached scrape result until it appears or timeout expires."""
    if poll_interval is None:
        poll_interval = settings.CACHE_INFLIGHT_POLL_INTERVAL

    elapsed = 0.0
    while elapsed < timeout:
        cached = await get_cached_scrape(url, formats)
        if cached is not None:
            logger.debug(f"Got cached result after waiting {elapsed:.1f}s for {url}")
            return cached
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    logger.debug(f"Timed out waiting {timeout}s for cached result for {url}")
    return None
