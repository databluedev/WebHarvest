import fnmatch
import logging
from urllib.parse import urlparse

import httpx
import redis.asyncio as aioredis
from robotexclusionrulesparser import RobotExclusionRulesParser

from app.config import settings
from app.schemas.crawl import CrawlRequest, ScrapeOptions
from app.schemas.scrape import ScrapeRequest
from app.services.scraper import scrape_url, scrape_url_fetch_only

logger = logging.getLogger(__name__)


class WebCrawler:
    """BFS web crawler with Redis-backed frontier and visited set."""

    def __init__(self, job_id: str, config: CrawlRequest, proxy_manager=None):
        self.job_id = job_id
        self.config = config
        self.base_url = config.url
        self.base_domain = urlparse(config.url).netloc
        self._robots_cache: dict[str, RobotExclusionRulesParser] = {}
        self._redis: aioredis.Redis | None = None
        self._proxy_manager = proxy_manager
        self._crawl_session = None

        # Redis keys for this crawl
        self._frontier_key = f"crawl:{job_id}:frontier"
        self._visited_key = f"crawl:{job_id}:visited"
        self._depth_key = f"crawl:{job_id}:depth"

    async def initialize(self):
        """Set up Redis connection, initial frontier, and persistent browser session."""
        # Create a fresh Redis connection for this crawl task
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

        await self._redis.sadd(self._frontier_key, self.base_url)
        await self._redis.hset(self._depth_key, self.base_url, 0)
        # Set TTL on all keys (24 hours)
        for key in [self._frontier_key, self._visited_key, self._depth_key]:
            await self._redis.expire(key, 86400)

        # Create persistent browser session for this crawl
        from app.services.browser import CrawlSession, browser_pool

        self._crawl_session = CrawlSession(browser_pool)
        proxy = None
        if self._proxy_manager:
            proxy_obj = self._proxy_manager.get_random()
            if proxy_obj:
                proxy = self._proxy_manager.to_playwright(proxy_obj)
        await self._crawl_session.start(proxy=proxy, target_url=self.base_url)

    async def get_next_url(self) -> tuple[str, int] | None:
        """Pop the next URL from the frontier. Returns (url, depth) or None."""
        url = await self._redis.spop(self._frontier_key)
        if not url:
            return None
        depth = await self._redis.hget(self._depth_key, url)
        return url, int(depth or 0)

    async def mark_visited(self, url: str):
        await self._redis.sadd(self._visited_key, url)

    async def is_visited(self, url: str) -> bool:
        return await self._redis.sismember(self._visited_key, url)

    async def get_visited_count(self) -> int:
        return await self._redis.scard(self._visited_key)

    async def get_frontier_size(self) -> int:
        return await self._redis.scard(self._frontier_key)

    async def add_to_frontier(self, urls: list[str], depth: int):
        """Add discovered URLs to the frontier after filtering."""
        for url in urls:
            if await self.is_visited(url):
                continue
            if not self._should_crawl(url, depth):
                continue
            if self.config.respect_robots_txt and not await self._is_allowed_by_robots(
                url
            ):
                continue

            visited_count = await self.get_visited_count()
            frontier_size = await self.get_frontier_size()
            if visited_count + frontier_size >= self.config.max_pages:
                break

            await self._redis.sadd(self._frontier_key, url)
            await self._redis.hset(self._depth_key, url, depth)

    # URL path segments that indicate low-value pages (login walls, account,
    # legal, empty shells).  Checked as substrings of the lowercased path.
    _LOW_VALUE_PATH_KEYWORDS = {
        "/signin", "/sign-in", "/sign_in",
        "/login", "/log-in", "/log_in",
        "/signup", "/sign-up", "/sign_up",
        "/register",
        "/account", "/my-account",
        "/cart", "/checkout", "/buy",
        "/wishlist", "/wish-list",
        "/help", "/support", "/contact-us", "/contact",
        "/terms", "/tos", "/privacy", "/legal", "/cookie-policy",
        "/affiliate", "/become-an-affiliate",
        "/seller", "/sell-on", "/global-selling",
        "/app-download", "/download-app",
        "/unsubscribe", "/preferences",
        "/404", "/error",
        "/auth/", "/oauth/", "/sso/",
    }

    # Query-string keys that signal non-content pages
    _LOW_VALUE_QUERY_KEYS = {
        "ref_", "tag", "utm_source", "utm_medium", "utm_campaign",
    }

    def _should_crawl(self, url: str, depth: int) -> bool:
        """Check if a URL should be crawled based on config filters."""
        parsed = urlparse(url)

        # Check depth
        if depth > self.config.max_depth:
            return False

        # Check domain (unless external links allowed)
        if not self.config.allow_external_links and parsed.netloc != self.base_domain:
            return False

        # Skip non-HTTP schemes
        if parsed.scheme not in ("http", "https"):
            return False

        # Skip common non-page extensions
        skip_extensions = {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".svg",
            ".webp",
            ".mp4",
            ".mp3",
            ".zip",
            ".tar",
            ".gz",
            ".css",
            ".js",
        }
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            return False

        # Skip low-value pages (login, account, help, legal, etc.)
        for kw in self._LOW_VALUE_PATH_KEYWORDS:
            if kw in path_lower:
                return False

        path = parsed.path

        # Check include paths
        if self.config.include_paths:
            if not any(
                fnmatch.fnmatch(path, pattern) for pattern in self.config.include_paths
            ):
                return False

        # Check exclude paths
        if self.config.exclude_paths:
            if any(
                fnmatch.fnmatch(path, pattern) for pattern in self.config.exclude_paths
            ):
                return False

        return True

    async def _is_allowed_by_robots(self, url: str) -> bool:
        """Check robots.txt for the given URL."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_cache:
            robots_url = f"{domain}/robots.txt"
            parser = RobotExclusionRulesParser()
            try:
                # Use curl_cffi for TLS impersonation, fall back to httpx
                text = ""
                try:
                    from curl_cffi.requests import AsyncSession

                    async with AsyncSession(impersonate="chrome124") as session:
                        resp = await session.get(
                            robots_url, timeout=10, allow_redirects=True
                        )
                        if resp.status_code == 200:
                            text = resp.text
                except Exception:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(robots_url)
                        if resp.status_code == 200:
                            text = resp.text
                if text:
                    parser.parse(text)
            except Exception:
                pass  # Network error = allow all, cache empty parser
            self._robots_cache[domain] = parser

        return self._robots_cache[domain].is_allowed("*", url)

    async def scrape_page(self, url: str) -> dict:
        """Scrape a single page using the crawler's scrape options."""
        opts = self.config.scrape_options or ScrapeOptions()

        # Always include "links" for BFS frontier expansion
        # Default ScrapeOptions already includes all formats
        formats = list(set(opts.formats) | {"links"})

        request = ScrapeRequest(
            url=url,
            formats=formats,
            only_main_content=opts.only_main_content,
            wait_for=opts.wait_for,
            timeout=opts.timeout,
            include_tags=opts.include_tags,
            exclude_tags=opts.exclude_tags,
            headers=getattr(opts, "headers", None),
            cookies=getattr(opts, "cookies", None),
            mobile=getattr(opts, "mobile", False),
        )

        result = await scrape_url(
            request,
            proxy_manager=self._proxy_manager,
            crawl_session=self._crawl_session,
        )

        # Use extracted links for frontier expansion
        discovered_links = result.links or []

        return {
            "scrape_data": result,
            "discovered_links": discovered_links,
        }

    async def fetch_page_only(self, url: str) -> dict | None:
        """Fetch-only phase for pipeline mode — returns raw data without extraction."""
        opts = self.config.scrape_options or ScrapeOptions()
        formats = list(set(opts.formats) | {"links"})

        request = ScrapeRequest(
            url=url,
            formats=formats,
            only_main_content=opts.only_main_content,
            wait_for=opts.wait_for,
            timeout=opts.timeout,
            include_tags=opts.include_tags,
            exclude_tags=opts.exclude_tags,
            headers=getattr(opts, "headers", None),
            cookies=getattr(opts, "cookies", None),
            mobile=getattr(opts, "mobile", False),
        )

        fetch_result = await scrape_url_fetch_only(
            request,
            proxy_manager=self._proxy_manager,
            crawl_session=self._crawl_session,
        )
        if fetch_result:
            fetch_result["request"] = request
        return fetch_result

    async def cleanup(self):
        """Remove Redis keys, close browser session, and close the connection."""
        if self._crawl_session:
            try:
                await self._crawl_session.stop()
            except Exception:
                pass
            self._crawl_session = None
        if self._redis:
            await self._redis.delete(
                self._frontier_key, self._visited_key, self._depth_key
            )
            await self._redis.aclose()
            self._redis = None
