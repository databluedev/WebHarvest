"""Unit tests for app.services.circuit_breaker — Redis-backed circuit breaker."""

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.circuit_breaker import (
    get_state,
    check_breaker,
    record_success,
    record_failure,
    CircuitBreakerOpenError,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_HALF_OPEN,
    CB_FAILURE_THRESHOLD,
    CB_OPEN_TIMEOUT,
)


class FakeRedis:
    """Minimal fake Redis for testing circuit breaker logic."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._zsets: dict[str, dict] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._store[key] = value

    async def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)
            self._sets.pop(key, None)
            self._zsets.pop(key, None)

    async def incr(self, key: str):
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val

    async def sismember(self, key: str, member: str):
        return member in self._sets.get(key, set())

    async def sadd(self, key: str, *members):
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for m in members:
            if m not in self._sets[key]:
                self._sets[key].add(m)
                added += 1
        return added

    async def zadd(self, key: str, mapping: dict):
        if key not in self._zsets:
            self._zsets[key] = {}
        self._zsets[key].update(mapping)

    async def zremrangebyscore(self, key: str, min_score, max_score):
        if key not in self._zsets:
            return 0
        to_remove = [
            k for k, v in self._zsets[key].items()
            if float(v) >= min_score and float(v) <= max_score
        ]
        for k in to_remove:
            del self._zsets[key][k]
        return len(to_remove)

    async def zcard(self, key: str):
        return len(self._zsets.get(key, {}))

    async def expire(self, key: str, ttl: int):
        pass

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    """Fake Redis pipeline that collects and executes commands."""

    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._commands = []

    def set(self, key, value, ex=None):
        self._commands.append(("set", key, value, ex))
        return self

    def delete(self, *keys):
        self._commands.append(("delete", *keys))
        return self

    def zadd(self, key, mapping):
        self._commands.append(("zadd", key, mapping))
        return self

    def zremrangebyscore(self, key, min_s, max_s):
        self._commands.append(("zremrangebyscore", key, min_s, max_s))
        return self

    def zcard(self, key):
        self._commands.append(("zcard", key))
        return self

    def expire(self, key, ttl):
        self._commands.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "set":
                await self._redis.set(cmd[1], cmd[2], ex=cmd[3])
                results.append(True)
            elif cmd[0] == "delete":
                await self._redis.delete(*cmd[1:])
                results.append(True)
            elif cmd[0] == "zadd":
                await self._redis.zadd(cmd[1], cmd[2])
                results.append(1)
            elif cmd[0] == "zremrangebyscore":
                count = await self._redis.zremrangebyscore(cmd[1], cmd[2], cmd[3])
                results.append(count)
            elif cmd[0] == "zcard":
                count = await self._redis.zcard(cmd[1])
                results.append(count)
            elif cmd[0] == "expire":
                results.append(True)
        return results


@pytest.fixture
def fake_redis():
    return FakeRedis()


class TestCircuitBreakerStates:
    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, fake_redis):
        """Default state for unknown domain is CLOSED."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            state = await get_state("example.com")
            assert state == STATE_CLOSED

    @pytest.mark.asyncio
    async def test_check_breaker_allows_closed(self, fake_redis):
        """check_breaker does not raise when CLOSED."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            await check_breaker("example.com")  # Should not raise

    @pytest.mark.asyncio
    async def test_failures_open_breaker(self, fake_redis):
        """After CB_FAILURE_THRESHOLD failures, breaker opens."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            for _ in range(CB_FAILURE_THRESHOLD):
                await record_failure("dead-site.com")

            state = await get_state("dead-site.com")
            assert state == STATE_OPEN

    @pytest.mark.asyncio
    async def test_open_breaker_rejects_requests(self, fake_redis):
        """check_breaker raises CircuitBreakerOpenError when OPEN."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            for _ in range(CB_FAILURE_THRESHOLD):
                await record_failure("dead-site.com")

            with pytest.raises(CircuitBreakerOpenError) as exc_info:
                await check_breaker("dead-site.com")
            assert exc_info.value.domain == "dead-site.com"

    @pytest.mark.asyncio
    async def test_success_resets_to_closed(self, fake_redis):
        """record_success resets breaker to CLOSED."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            for _ in range(CB_FAILURE_THRESHOLD):
                await record_failure("flaky-site.com")

            state = await get_state("flaky-site.com")
            assert state == STATE_OPEN

            await record_success("flaky-site.com")
            state = await get_state("flaky-site.com")
            assert state == STATE_CLOSED

    @pytest.mark.asyncio
    async def test_half_open_transition(self, fake_redis):
        """After timeout, OPEN transitions to HALF_OPEN."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            # Open the breaker
            for _ in range(CB_FAILURE_THRESHOLD):
                await record_failure("slow-site.com")

            # Manually set opened_at to past (simulate timeout)
            fake_redis._store["cb:slow-site.com:opened_at"] = str(
                time.time() - CB_OPEN_TIMEOUT - 1
            )

            state = await get_state("slow-site.com")
            assert state == STATE_HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_allows_probe(self, fake_redis):
        """In HALF_OPEN state, one probe request is allowed."""
        with patch("app.services.circuit_breaker.redis_client", fake_redis):
            for _ in range(CB_FAILURE_THRESHOLD):
                await record_failure("probe-site.com")

            # Simulate transition to HALF_OPEN
            fake_redis._store["cb:probe-site.com:opened_at"] = str(
                time.time() - CB_OPEN_TIMEOUT - 1
            )

            # First call should succeed (probe)
            await check_breaker("probe-site.com")

            # Second call should be rejected
            with pytest.raises(CircuitBreakerOpenError):
                await check_breaker("probe-site.com")


class TestCircuitBreakerErrorCode:
    def test_error_includes_domain(self):
        """CircuitBreakerOpenError includes domain in message."""
        err = CircuitBreakerOpenError("test.com", 15.0)
        assert "test.com" in str(err)
        assert err.domain == "test.com"
        assert err.retry_after == 15.0
