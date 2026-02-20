"""Resilient Redis client with graceful degradation.

When Redis is unavailable, operations return None/defaults instead of
raising exceptions. This allows scraping/crawling to continue without
caching or deduplication.
"""

import asyncio
import logging
import time

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class ResilientRedis:
    """Wraps an async Redis client with automatic reconnection and degradation.

    - All operations catch ConnectionError/TimeoutError and return defaults
    - Auto-reconnects with exponential backoff (1s, 2s, 4s, ..., max 30s)
    - Circuit breaker: after 5 consecutive failures, skip Redis for 10s
    """

    CB_THRESHOLD = 5
    CB_COOLDOWN = 10.0
    MAX_BACKOFF = 30.0

    def __init__(self):
        self._client: aioredis.Redis | None = None
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._reconnect_delay = 1.0

    def _create_client(self) -> aioredis.Redis:
        return aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _is_circuit_open(self) -> bool:
        if self._consecutive_failures >= self.CB_THRESHOLD:
            if time.monotonic() < self._circuit_open_until:
                return True
            # Cooldown expired, allow a probe
            self._consecutive_failures = 0
        return False

    def _record_success(self):
        self._consecutive_failures = 0
        self._reconnect_delay = 1.0

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.CB_THRESHOLD:
            self._circuit_open_until = time.monotonic() + self.CB_COOLDOWN
            logger.warning(
                f"Redis circuit breaker OPEN — skipping for {self.CB_COOLDOWN}s"
            )

    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        try:
            if self._client:
                await self._client.close()
        except Exception:
            pass
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self.MAX_BACKOFF)
        self._client = self._create_client()

    async def _safe_op(self, op_name, coro_func, *args, default=None, **kwargs):
        """Execute a Redis operation with degradation on failure."""
        if self._is_circuit_open():
            return default

        try:
            result = await coro_func(*args, **kwargs)
            self._record_success()
            return result
        except (
            aioredis.ConnectionError,
            aioredis.TimeoutError,
            ConnectionRefusedError,
            OSError,
        ) as e:
            self._record_failure()
            logger.warning(f"Redis {op_name} failed (degraded): {e}")
            # Try to reconnect for next call
            try:
                await self._reconnect()
            except Exception:
                pass
            return default
        except Exception as e:
            # Non-connection errors still propagate
            logger.debug(f"Redis {op_name} error: {e}")
            raise

    # --- Proxy all common Redis operations ---

    async def get(self, key, *args, **kwargs):
        return await self._safe_op("get", self.client.get, key, *args, **kwargs)

    async def set(self, key, value, *args, **kwargs):
        return await self._safe_op(
            "set", self.client.set, key, value, *args, default=False, **kwargs
        )

    async def delete(self, *keys):
        return await self._safe_op("delete", self.client.delete, *keys, default=0)

    async def exists(self, *keys):
        return await self._safe_op("exists", self.client.exists, *keys, default=0)

    async def incr(self, key, amount=1):
        return await self._safe_op("incr", self.client.incr, key, amount, default=0)

    async def decr(self, key, amount=1):
        return await self._safe_op("decr", self.client.decr, key, amount, default=0)

    async def expire(self, key, seconds):
        return await self._safe_op(
            "expire", self.client.expire, key, seconds, default=False
        )

    async def ttl(self, key):
        return await self._safe_op("ttl", self.client.ttl, key, default=-2)

    async def lpush(self, key, *values):
        return await self._safe_op("lpush", self.client.lpush, key, *values, default=0)

    async def lrange(self, key, start, end):
        return await self._safe_op(
            "lrange", self.client.lrange, key, start, end, default=[]
        )

    async def llen(self, key):
        return await self._safe_op("llen", self.client.llen, key, default=0)

    async def lrem(self, key, count, value):
        return await self._safe_op(
            "lrem", self.client.lrem, key, count, value, default=0
        )

    async def ltrim(self, key, start, end):
        return await self._safe_op(
            "ltrim", self.client.ltrim, key, start, end, default=False
        )

    async def sadd(self, key, *values):
        return await self._safe_op("sadd", self.client.sadd, key, *values, default=0)

    async def sismember(self, key, value):
        return await self._safe_op(
            "sismember", self.client.sismember, key, value, default=False
        )

    async def smembers(self, key):
        return await self._safe_op("smembers", self.client.smembers, key, default=set())

    async def srem(self, key, *values):
        return await self._safe_op("srem", self.client.srem, key, *values, default=0)

    async def zadd(self, key, mapping, *args, **kwargs):
        return await self._safe_op(
            "zadd", self.client.zadd, key, mapping, *args, default=0, **kwargs
        )

    async def zremrangebyscore(self, key, min_score, max_score):
        return await self._safe_op(
            "zremrangebyscore",
            self.client.zremrangebyscore,
            key,
            min_score,
            max_score,
            default=0,
        )

    async def zcard(self, key):
        return await self._safe_op("zcard", self.client.zcard, key, default=0)

    async def hset(self, name, key=None, value=None, mapping=None):
        if mapping:
            return await self._safe_op(
                "hset", self.client.hset, name, mapping=mapping, default=0
            )
        return await self._safe_op(
            "hset", self.client.hset, name, key, value, default=0
        )

    async def hget(self, name, key):
        return await self._safe_op("hget", self.client.hget, name, key)

    async def hgetall(self, name):
        return await self._safe_op("hgetall", self.client.hgetall, name, default={})

    async def hdel(self, name, *keys):
        return await self._safe_op("hdel", self.client.hdel, name, *keys, default=0)

    async def setex(self, name, time_val, value):
        return await self._safe_op(
            "setex", self.client.setex, name, time_val, value, default=False
        )

    async def ping(self):
        return await self._safe_op("ping", self.client.ping, default=False)

    def pipeline(self):
        """Return the underlying pipeline for batch operations.

        Note: Pipeline operations are NOT wrapped in degradation — callers
        should handle exceptions when using pipelines directly.
        """
        return self.client.pipeline()

    async def close(self):
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None


# Module-level singleton
redis_client = ResilientRedis()


async def get_redis() -> ResilientRedis:
    return redis_client
