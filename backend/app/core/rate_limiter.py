import time

from app.core.redis import redis_client


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
