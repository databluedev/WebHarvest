import time

from app.core.redis import redis_client


class RateLimitInfo:
    """Rate limit check result with metadata for response headers."""

    __slots__ = ("allowed", "remaining", "limit", "reset")

    def __init__(self, allowed: bool, remaining: int, limit: int, reset: int):
        self.allowed = allowed
        self.remaining = remaining
        self.limit = limit
        self.reset = reset  # Unix timestamp when the window resets


async def check_rate_limit(key: str, limit: int, window: int = 60) -> tuple[bool, int]:
    """
    Sliding window rate limiter using Redis.
    Returns (is_allowed, remaining_requests).
    """
    now = time.time()
    pipe = redis_client.pipeline()

    # Remove old entries outside the window
    pipe.zremrangebyscore(key, 0, now - window)
    # Add current request
    pipe.zadd(key, {str(now): now})
    # Count requests in window
    pipe.zcard(key)
    # Set expiry on the key
    pipe.expire(key, window)

    results = await pipe.execute()
    request_count = results[2]

    if request_count > limit:
        return False, 0

    return True, limit - request_count


async def check_rate_limit_full(
    key: str, limit: int, window: int = 60
) -> RateLimitInfo:
    """
    Sliding window rate limiter returning full info for response headers.
    """
    now = time.time()
    pipe = redis_client.pipeline()

    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)

    results = await pipe.execute()
    request_count = results[2]
    reset_at = int(now) + window

    if request_count > limit:
        return RateLimitInfo(allowed=False, remaining=0, limit=limit, reset=reset_at)

    return RateLimitInfo(
        allowed=True,
        remaining=limit - request_count,
        limit=limit,
        reset=reset_at,
    )
