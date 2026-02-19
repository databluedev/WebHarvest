"""Redis-backed domain strategy memory.

Remembers which scraping strategy works for each domain so repeat visits
can skip failing tiers and jump straight to the last known working strategy.

Redis key: "strategy:{domain}" | TTL: configurable (default 24 hours)
Value: JSON with last_success_strategy, last_success_tier, fail counts, timing
"""

import json
import logging
import time
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)


def _get_domain(url: str) -> str:
    """Extract bare domain from URL (strips www.)."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _redis_key(domain: str) -> str:
    return f"strategy:{domain}"


async def _get_redis():
    """Get the shared Redis connection."""
    try:
        from app.core.redis import get_redis
        return await get_redis()
    except Exception:
        return None


async def get_domain_strategy(url: str) -> dict | None:
    """Fetch cached strategy data for a domain.

    Returns dict with keys:
        last_success_strategy: str  (e.g. "curl_cffi:chrome124")
        last_success_tier: int      (0-4)
        fail_count_tier1: int
        fail_count_tier2: int
        last_success_time: float
        avg_success_ms: float
    Or None if no data cached.
    """
    domain = _get_domain(url)
    if not domain:
        return None

    redis = await _get_redis()
    if not redis:
        return None

    try:
        raw = await redis.get(_redis_key(domain))
        if raw:
            data = json.loads(raw)
            logger.debug(f"Strategy cache hit for {domain}: tier={data.get('last_success_tier')}, strategy={data.get('last_success_strategy')}")
            return data
    except Exception as e:
        logger.debug(f"Strategy cache read error for {domain}: {e}")

    return None


async def record_strategy_result(
    url: str,
    strategy: str,
    tier: int,
    success: bool,
    time_ms: float,
) -> None:
    """Record strategy result for a domain.

    Args:
        url: The scraped URL
        strategy: Strategy name (e.g. "curl_cffi:chrome124", "chromium_stealth")
        tier: Tier number (0-4)
        success: Whether this strategy produced usable content
        time_ms: Time taken in milliseconds
    """
    domain = _get_domain(url)
    if not domain:
        return

    redis = await _get_redis()
    if not redis:
        return

    key = _redis_key(domain)
    ttl = settings.STRATEGY_CACHE_TTL_SECONDS

    try:
        # Read existing data
        raw = await redis.get(key)
        data = json.loads(raw) if raw else {
            "fail_count_tier1": 0,
            "fail_count_tier2": 0,
        }

        if success:
            data["last_success_strategy"] = strategy
            data["last_success_tier"] = tier
            data["last_success_time"] = time.time()
            # Exponential moving average for timing
            prev_avg = data.get("avg_success_ms", time_ms)
            data["avg_success_ms"] = prev_avg * 0.7 + time_ms * 0.3
            # Reset fail counts for lower tiers on success
            if tier <= 1:
                data["fail_count_tier1"] = 0
            if tier <= 2:
                data["fail_count_tier2"] = 0
        else:
            # Increment fail counts
            if tier <= 1:
                data["fail_count_tier1"] = data.get("fail_count_tier1", 0) + 1
            elif tier <= 2:
                data["fail_count_tier2"] = data.get("fail_count_tier2", 0) + 1

        await redis.set(key, json.dumps(data), ex=ttl)
    except Exception as e:
        logger.debug(f"Strategy cache write error for {domain}: {e}")


def get_starting_tier(strategy_data: dict | None, is_hard_site: bool) -> int:
    """Decide which tier to start from based on cached strategy data.

    Returns:
        0: Start from tier 0 (try cached strategy first)
        1: Start from tier 1 (HTTP strategies)
        2: Start from tier 2 (browser strategies)
        3: Start from tier 3 (heavy strategies)
    """
    if not strategy_data:
        return 1  # No cache, start from tier 1

    last_tier = strategy_data.get("last_success_tier")
    if last_tier is not None:
        # We have a cached success — start from tier 0 (cache hit attempt)
        return 0

    # No success recorded but we have fail data
    tier1_fails = strategy_data.get("fail_count_tier1", 0)
    tier2_fails = strategy_data.get("fail_count_tier2", 0)

    if tier1_fails >= 3 and tier2_fails >= 3:
        return 3  # Skip straight to heavy strategies
    if tier1_fails >= 3:
        return 2  # Skip HTTP, go to browsers

    return 1
