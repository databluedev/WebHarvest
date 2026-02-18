import redis.asyncio as aioredis

from app.config import settings

redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
)


async def get_redis() -> aioredis.Redis:
    return redis_client
