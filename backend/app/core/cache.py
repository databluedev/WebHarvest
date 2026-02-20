import hashlib
import json
import logging

from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

CACHE_PREFIX = "cache:scrape:"


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
