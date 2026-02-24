import logging
import random
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client as _redis

logger = logging.getLogger(__name__)

# --- Builtin proxy pool (cached in-memory, refreshed from API) ---
_builtin_proxy_cache: list[str] = []
_builtin_proxy_cache_time: float = 0
_BUILTIN_CACHE_TTL = 600  # 10 minutes


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
                ProxyConfig.is_active == True,  # noqa: E712
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


async def _fetch_proxy_list(api_url: str) -> list[str]:
    """Fetch proxy list from API (GeoNode, ProxyScrape, etc.).

    Supports JSON responses with common formats:
    - {"data": [{"protocols": ["socks5"], "ip": "...", "port": "..."}, ...]}  (GeoNode)
    - [{"ip": "...", "port": ..., "type": "..."}, ...]
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json()

        proxies = []
        # GeoNode format: {"data": [...]}
        items = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []

        for item in items:
            ip = item.get("ip", "")
            port = item.get("port", "")
            if not ip or not port:
                continue
            # Determine protocol
            protocols = item.get("protocols", [])
            if isinstance(protocols, list) and protocols:
                proto = protocols[0]
            else:
                proto = item.get("type", item.get("protocol", "http"))
            proxy_url = f"{proto}://{ip}:{port}"
            proxies.append(proxy_url)

        logger.info(f"Fetched {len(proxies)} proxies from API")
        return proxies
    except Exception as e:
        logger.warning(f"Failed to fetch proxy list from {api_url}: {e}")
        return []


async def get_builtin_proxy_manager() -> ProxyManager | None:
    """Get a ProxyManager from builtin proxy config (env vars).

    Sources (in order of priority):
    1. BUILTIN_PROXY_URL — comma-separated static proxy URLs
    2. BUILTIN_PROXY_LIST_URL — API endpoint returning JSON proxy list (cached 10 min)

    Returns None if no builtin proxies are configured.
    """
    global _builtin_proxy_cache, _builtin_proxy_cache_time

    from app.config import settings

    urls: list[str] = []

    # 1. Static URLs from env var (comma-separated)
    if settings.BUILTIN_PROXY_URL:
        urls.extend(u.strip() for u in settings.BUILTIN_PROXY_URL.split(",") if u.strip())

    # 2. Dynamic list from API (cached)
    if settings.BUILTIN_PROXY_LIST_URL:
        now = time.time()
        if not _builtin_proxy_cache or (now - _builtin_proxy_cache_time) > _BUILTIN_CACHE_TTL:
            fresh = await _fetch_proxy_list(settings.BUILTIN_PROXY_LIST_URL)
            if fresh:
                _builtin_proxy_cache = fresh
                _builtin_proxy_cache_time = now
        urls.extend(_builtin_proxy_cache)

    if not urls:
        return None

    return ProxyManager.from_urls(urls)
