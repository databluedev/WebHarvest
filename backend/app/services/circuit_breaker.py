"""Redis-backed circuit breaker for external domains.

States: CLOSED → OPEN → HALF_OPEN
- CLOSED: requests flow normally; failures are tracked
- OPEN: requests are rejected immediately for a cooldown period
- HALF_OPEN: one probe request is allowed; success resets, failure re-opens
"""

import logging
import time

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

# Circuit breaker configuration
CB_FAILURE_THRESHOLD = 5  # failures to trip the breaker
CB_FAILURE_WINDOW = 60  # seconds to track failures
CB_OPEN_TIMEOUT = 30  # seconds before transitioning to HALF_OPEN
CB_HALF_OPEN_MAX_PROBES = 1  # concurrent probes allowed in HALF_OPEN

# State constants
STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open for a domain."""

    def __init__(self, domain: str, retry_after: float = 0):
        self.domain = domain
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker open for {domain}, retry after {retry_after:.0f}s")


def _key_failures(domain: str) -> str:
    return f"cb:{domain}:failures"


def _key_state(domain: str) -> str:
    return f"cb:{domain}:state"


def _key_opened_at(domain: str) -> str:
    return f"cb:{domain}:opened_at"


def _key_half_open_probes(domain: str) -> str:
    return f"cb:{domain}:probes"


async def get_state(domain: str) -> str:
    """Get the current circuit breaker state for a domain."""
    try:
        state = await redis_client.get(_key_state(domain))
        if state is None:
            return STATE_CLOSED

        # Check if OPEN state has expired → transition to HALF_OPEN
        if state == STATE_OPEN:
            opened_at = await redis_client.get(_key_opened_at(domain))
            if opened_at and (time.time() - float(opened_at)) >= CB_OPEN_TIMEOUT:
                await redis_client.set(
                    _key_state(domain), STATE_HALF_OPEN, ex=CB_OPEN_TIMEOUT * 2
                )
                await redis_client.delete(_key_half_open_probes(domain))
                return STATE_HALF_OPEN
        return state
    except Exception:
        # If Redis is down, default to closed (allow requests)
        return STATE_CLOSED


async def check_breaker(domain: str) -> None:
    """Check if a request to this domain should be allowed.

    Raises CircuitBreakerOpenError if the breaker is open.
    In HALF_OPEN state, allows one probe request.
    """
    state = await get_state(domain)

    if state == STATE_CLOSED:
        return  # All good

    if state == STATE_OPEN:
        opened_at_str = await redis_client.get(_key_opened_at(domain))
        retry_after = 0.0
        if opened_at_str:
            retry_after = max(0, CB_OPEN_TIMEOUT - (time.time() - float(opened_at_str)))
        raise CircuitBreakerOpenError(domain, retry_after)

    if state == STATE_HALF_OPEN:
        # Allow limited probes
        probes = await redis_client.incr(_key_half_open_probes(domain))
        if probes > CB_HALF_OPEN_MAX_PROBES:
            raise CircuitBreakerOpenError(domain, CB_OPEN_TIMEOUT)
        return  # Probe allowed


async def record_success(domain: str) -> None:
    """Record a successful request — resets the breaker to CLOSED."""
    try:
        state = await get_state(domain)
        if state in (STATE_HALF_OPEN, STATE_OPEN):
            logger.info(f"Circuit breaker reset to CLOSED for {domain}")
        # Reset everything
        pipe = redis_client.pipeline()
        pipe.delete(_key_state(domain))
        pipe.delete(_key_failures(domain))
        pipe.delete(_key_opened_at(domain))
        pipe.delete(_key_half_open_probes(domain))
        await pipe.execute()
    except Exception as e:
        logger.debug(f"Circuit breaker record_success failed for {domain}: {e}")


async def record_failure(domain: str) -> None:
    """Record a failed request. If threshold exceeded, open the breaker."""
    try:
        state = await get_state(domain)

        if state == STATE_HALF_OPEN:
            # Probe failed — reopen
            await _open_breaker(domain)
            return

        # Increment failure count in sliding window
        key = _key_failures(domain)
        now = time.time()
        pipe = redis_client.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.zremrangebyscore(key, 0, now - CB_FAILURE_WINDOW)
        pipe.zcard(key)
        pipe.expire(key, CB_FAILURE_WINDOW * 2)
        results = await pipe.execute()
        failure_count = results[2]

        if failure_count >= CB_FAILURE_THRESHOLD:
            await _open_breaker(domain)
    except Exception as e:
        logger.debug(f"Circuit breaker record_failure failed for {domain}: {e}")


async def _open_breaker(domain: str) -> None:
    """Transition the breaker to OPEN state."""
    logger.warning(
        f"Circuit breaker OPENED for {domain} "
        f"(threshold={CB_FAILURE_THRESHOLD}, cooldown={CB_OPEN_TIMEOUT}s)"
    )
    pipe = redis_client.pipeline()
    pipe.set(_key_state(domain), STATE_OPEN, ex=CB_OPEN_TIMEOUT * 3)
    pipe.set(_key_opened_at(domain), str(time.time()), ex=CB_OPEN_TIMEOUT * 3)
    pipe.delete(_key_failures(domain))
    await pipe.execute()
