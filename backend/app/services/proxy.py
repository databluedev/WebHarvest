import logging
import random
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client as _redis

logger = logging.getLogger(__name__)


@dataclass
class Proxy:
    protocol: str  # http, https, socks5
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    @classmethod
    def from_url(cls, url: str) -> "Proxy":
        """Parse a proxy URL into a Proxy object."""
        parsed = urlparse(url)
        return cls(
            protocol=parsed.scheme or "http",
            host=parsed.hostname or "",
            port=parsed.port or 8080,
            username=parsed.username,
            password=parsed.password,
        )


class ProxyManager:
    """Manages a pool of proxies for rotating use."""

    def __init__(self, proxies: list[Proxy] | None = None):
        self._proxies = proxies or []

    @classmethod
    async def from_user(cls, db: AsyncSession, user_id: UUID) -> "ProxyManager":
        """Load active proxies from database for a user."""
        from app.models.proxy_config import ProxyConfig

        result = await db.execute(
            select(ProxyConfig).where(
                ProxyConfig.user_id == user_id,
                ProxyConfig.is_active == True,
            )
        )
        configs = result.scalars().all()

        proxies = [Proxy.from_url(c.proxy_url) for c in configs]
        return cls(proxies)

    @classmethod
    def from_urls(cls, urls: list[str]) -> "ProxyManager":
        """Create a ProxyManager from a list of proxy URLs."""
        proxies = [Proxy.from_url(url) for url in urls if url.strip()]
        return cls(proxies)

    @property
    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    def get_random(self) -> Proxy | None:
        """Get a random proxy from the pool."""
        if not self._proxies:
            return None
        return random.choice(self._proxies)

    async def mark_failed(self, proxy: Proxy) -> None:
        """Increment failure count for a proxy (10-min TTL)."""
        key = f"proxy:fail:{proxy.host}:{proxy.port}"
        await _redis.incr(key)
        await _redis.expire(key, 600)

    async def get_random_weighted(self) -> Proxy | None:
        """Get a random proxy weighted by fewer failures."""
        if not self._proxies:
            return None

        weights = []
        for p in self._proxies:
            key = f"proxy:fail:{p.host}:{p.port}"
            fails = await _redis.get(key)
            fail_count = int(fails) if fails else 0
            # Weight = 1 / (1 + fail_count) — fewer failures = higher weight
            weights.append(1.0 / (1.0 + fail_count))

        total = sum(weights)
        if total == 0:
            return random.choice(self._proxies)

        r = random.uniform(0, total)
        cumulative = 0.0
        for proxy, weight in zip(self._proxies, weights):
            cumulative += weight
            if r <= cumulative:
                return proxy

        return self._proxies[-1]

    @staticmethod
    def to_playwright(proxy: Proxy) -> dict:
        """Convert a Proxy to Playwright proxy format."""
        server = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        result = {"server": server}
        if proxy.username:
            result["username"] = proxy.username
        if proxy.password:
            result["password"] = proxy.password
        return result

    @staticmethod
    def to_httpx(proxy: Proxy) -> str:
        """Convert a Proxy to httpx proxy URL string."""
        if proxy.username and proxy.password:
            return f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        return f"{proxy.protocol}://{proxy.host}:{proxy.port}"

    @staticmethod
    def mask_url(url: str) -> str:
        """Mask credentials in a proxy URL for display."""
        parsed = urlparse(url)
        if parsed.username:
            masked_user = parsed.username[:2] + "***"
            masked_pass = "***" if parsed.password else ""
            netloc = f"{masked_user}:{masked_pass}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
        return url
