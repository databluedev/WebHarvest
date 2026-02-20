"""
Redis response cache for completed job status endpoints.

Completed/failed jobs are immutable — their data never changes.
We cache the full serialized JSON response in Redis so subsequent
requests bypass DB, ORM, Pydantic, and JSON serialization entirely.

First load: DB → serialize → cache → return  (~normal speed)
Subsequent loads: Redis → return  (< 5ms)
"""

import json
import logging

from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

CACHE_PREFIX = "cache:job:"
CACHE_TTL = 3600  # 1 hour (completed jobs never change)


def _cache_key(job_id: str, suffix: str = "") -> str:
    key = f"{CACHE_PREFIX}{job_id}"
    if suffix:
        key += f":{suffix}"
    return key


async def get_cached_response(job_id: str, suffix: str = "") -> str | None:
    """Get cached JSON response string. Returns None if not cached."""
    if not settings.CACHE_ENABLED:
        return None
    try:
        data = await redis_client.get(_cache_key(job_id, suffix))
        if data:
            logger.debug(f"Job cache hit: {job_id}")
        return data
    except Exception as e:
        logger.warning(f"Job cache get failed: {e}")
        return None


async def set_cached_response(job_id: str, response_data: dict, suffix: str = "") -> None:
    """Cache a serialized JSON response for a completed job."""
    if not settings.CACHE_ENABLED:
        return
    try:
        serialized = json.dumps(response_data, default=str)
        await redis_client.setex(
            _cache_key(job_id, suffix), CACHE_TTL, serialized
        )
        logger.debug(f"Job cache set: {job_id} (TTL={CACHE_TTL}s)")
    except Exception as e:
        logger.warning(f"Job cache set failed: {e}")


async def invalidate_cache(job_id: str) -> None:
    """Invalidate all cached responses for a job (e.g., on cancel)."""
    try:
        pattern = f"{CACHE_PREFIX}{job_id}*"
        keys = []
        async for key in redis_client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await redis_client.delete(*keys)
            logger.debug(f"Job cache invalidated: {job_id} ({len(keys)} keys)")
    except Exception as e:
        logger.warning(f"Job cache invalidate failed: {e}")
