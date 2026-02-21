"""
Cross-user URL-based cache for all modes (scrape, map, search, crawl).

Every mode stores results in Redis keyed by SHA256(url + relevant params).
When any user requests the same URL with the same params, the cached result
is returned instantly — no job, no worker, no waiting.

Redis keys:
  cache:scrape:{hash}  → single-page scrape result
  cache:map:{hash}     → list of discovered URLs
  cache:search:{hash}  → list of search results with scraped content
  cache:crawl:{hash}   → list of crawled page results
"""

import hashlib
import json
import logging

from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic cache helpers — all modes use these
# ---------------------------------------------------------------------------

async def get_url_cache(prefix: str, key_data: str) -> dict | list | None:
    """Retrieve a cached result by mode prefix and key data. Returns None on miss."""
    if not settings.CACHE_ENABLED:
        return None
    try:
        digest = hashlib.sha256(key_data.encode()).hexdigest()
        key = f"{prefix}{digest}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"Cache hit: {prefix} key={key_data[:80]}")
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache get failed ({prefix}): {e}")
    return None


async def set_url_cache(
    prefix: str, key_data: str, data: dict | list, ttl: int | None = None
) -> None:
    """Store a result in the cross-user cache."""
    if not settings.CACHE_ENABLED:
        return
    try:
        digest = hashlib.sha256(key_data.encode()).hexdigest()
        key = f"{prefix}{digest}"
        ttl = ttl or settings.CACHE_TTL_SECONDS
        serialized = json.dumps(data, default=str)
        # Skip caching if data is excessively large (>10MB) to protect Redis
        if len(serialized) > 10_000_000:
            logger.debug(f"Skipping cache — data too large ({len(serialized)} bytes)")
            return
        await redis_client.setex(key, ttl, serialized)
        logger.debug(f"Cache set: {prefix} (TTL={ttl}s, size={len(serialized)})")
    except Exception as e:
        logger.warning(f"Cache set failed ({prefix}): {e}")


# ---------------------------------------------------------------------------
# Mode-specific helpers — build cache keys from request params
# ---------------------------------------------------------------------------

SCRAPE_PREFIX = "cache:scrape:"
MAP_PREFIX = "cache:map:"
SEARCH_PREFIX = "cache:search:"
CRAWL_PREFIX = "cache:crawl:"


def _scrape_key_data(url: str, formats: list[str]) -> str:
    return f"{url}:{','.join(sorted(formats))}"


def _map_key_data(url: str, limit: int, include_subdomains: bool, use_sitemap: bool, search: str | None) -> str:
    return f"{url}:{limit}:{include_subdomains}:{use_sitemap}:{search or ''}"


def _search_key_data(query: str, num_results: int, engine: str, formats: list[str]) -> str:
    return f"{query}:{num_results}:{engine}:{','.join(sorted(formats))}"


def _crawl_key_data(url: str, max_pages: int, max_depth: int) -> str:
    return f"{url}:{max_pages}:{max_depth}"


# --- Scrape ---

async def get_cached_scrape(url: str, formats: list[str]) -> dict | None:
    return await get_url_cache(SCRAPE_PREFIX, _scrape_key_data(url, formats))


async def set_cached_scrape(url: str, formats: list[str], data: dict, ttl: int | None = None) -> None:
    await set_url_cache(SCRAPE_PREFIX, _scrape_key_data(url, formats), data, ttl)


# --- Map ---

async def get_cached_map(url: str, limit: int, include_subdomains: bool, use_sitemap: bool, search: str | None) -> list | None:
    return await get_url_cache(MAP_PREFIX, _map_key_data(url, limit, include_subdomains, use_sitemap, search))


async def set_cached_map(url: str, limit: int, include_subdomains: bool, use_sitemap: bool, search: str | None, data: list, ttl: int | None = None) -> None:
    await set_url_cache(MAP_PREFIX, _map_key_data(url, limit, include_subdomains, use_sitemap, search), data, ttl)


# --- Search ---

async def get_cached_search(query: str, num_results: int, engine: str, formats: list[str]) -> list | None:
    return await get_url_cache(SEARCH_PREFIX, _search_key_data(query, num_results, engine, formats))


async def set_cached_search(query: str, num_results: int, engine: str, formats: list[str], data: list, ttl: int | None = None) -> None:
    await set_url_cache(SEARCH_PREFIX, _search_key_data(query, num_results, engine, formats), data, ttl)


# --- Crawl ---

async def get_cached_crawl(url: str, max_pages: int, max_depth: int) -> list | None:
    return await get_url_cache(CRAWL_PREFIX, _crawl_key_data(url, max_pages, max_depth))


async def set_cached_crawl(url: str, max_pages: int, max_depth: int, data: list, ttl: int | None = None) -> None:
    await set_url_cache(CRAWL_PREFIX, _crawl_key_data(url, max_pages, max_depth), data, ttl)
