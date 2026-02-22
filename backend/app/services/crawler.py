import fnmatch
import logging
import re
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
    """BFS web crawler with Redis-backed LIST frontier (Firecrawl-style).

    The frontier uses a Redis LIST (RPUSH/LPOP) for plain FIFO BFS.
    A companion SET tracks queued URLs (normalized) to prevent duplicate
    insertions.  Deduplication relies solely on URL normalization — no
    content fingerprinting.
    """

    @staticmethod
    def _strip_www(domain: str) -> str:
        """Strip www. prefix for domain comparison."""
        d = domain.lower()
        return d[4:] if d.startswith("www.") else d

    def __init__(self, job_id: str, config: CrawlRequest, proxy_manager=None):
        self.job_id = job_id
        self.config = config
        self.base_url = config.url
        self.base_domain = urlparse(config.url).netloc
        # Normalized domain for comparison (strip www. so www.x.com == x.com)
        self._base_domain_norm = self._strip_www(self.base_domain)
        self._robots_cache: dict[str, RobotExclusionRulesParser] = {}
        self._redis: aioredis.Redis | None = None
        self._proxy_manager = proxy_manager
        self._crawl_session = None

        # Redis keys for this crawl
        self._frontier_key = f"crawl:{job_id}:frontier"   # LIST (FIFO queue)
        self._queued_key = f"crawl:{job_id}:queued"        # SET  (dedup guard)
        self._visited_key = f"crawl:{job_id}:visited"
        self._depth_key = f"crawl:{job_id}:depth"

    async def initialize(self):
        """Set up Redis connection, initial frontier, and persistent browser session.

        Frontier seeding strategy (Firecrawl-style):
        1. Start URL — always first in the FIFO queue
        2. Sitemap discovery — fetch robots.txt + sitemap.xml, append URLs
        3. BFS link extraction fills the rest during crawl
        """
        # Create a fresh Redis connection for this crawl task
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

        # Seed the frontier with the start URL (first in FIFO)
        from app.services.dedup import normalize_url
        start_norm = normalize_url(self.base_url)
        await self._redis.rpush(self._frontier_key, start_norm)
        await self._redis.sadd(self._queued_key, start_norm)
        await self._redis.hset(self._depth_key, start_norm, 0)
        # Set TTL on all keys (24 hours)
        for key in [self._frontier_key, self._queued_key, self._visited_key, self._depth_key]:
            await self._redis.expire(key, 86400)

        # Sitemap-first seeding (Firecrawl pattern): discover URLs from
        # sitemap.xml and robots.txt Sitemap: directives.  Runs before
        # browser init so the frontier is rich from the start.
        await self._seed_from_sitemaps()

        # Create persistent browser session for this crawl
        from app.services.browser import CrawlSession, browser_pool

        self._crawl_session = CrawlSession(browser_pool)
        proxy = None
        if self._proxy_manager:
            proxy_obj = self._proxy_manager.get_random()
            if proxy_obj:
                proxy = self._proxy_manager.to_playwright(proxy_obj)
        await self._crawl_session.start(proxy=proxy, target_url=self.base_url)

    async def _seed_from_sitemaps(self):
        """Seed the crawl frontier from sitemap.xml (Firecrawl pattern).

        Discovers URLs from robots.txt Sitemap: directives and common sitemap
        locations. URLs are appended to the BFS LIST frontier in discovery order.
        """
        try:
            from app.services.mapper import _parse_sitemaps
            from app.services.dedup import normalize_url

            sitemap_links = await _parse_sitemaps(self.base_url)
            if not sitemap_links:
                logger.debug(f"No sitemap URLs found for {self.base_url}")
                return

            added = 0
            max_seed = self.config.max_pages * 5  # Cap to avoid huge frontiers
            for link in sitemap_links:
                if added >= max_seed:
                    break
                url = link.url
                norm = normalize_url(url)
                # Skip if already queued or visited
                if await self._redis.sismember(self._queued_key, norm):
                    continue
                if await self.is_visited(norm):
                    continue
                if not self._should_crawl(url, depth=1):
                    continue

                await self._redis.rpush(self._frontier_key, norm)
                await self._redis.sadd(self._queued_key, norm)
                await self._redis.hset(self._depth_key, norm, 1)
                added += 1

            if added:
                logger.info(
                    f"Sitemap seeding: added {added} URLs from "
                    f"{len(sitemap_links)} sitemap entries for {self.base_url}"
                )
        except Exception as e:
            logger.warning(f"Sitemap seeding failed for {self.base_url}: {e}")
            # Non-fatal — BFS still works via link extraction

    async def get_next_url(self) -> tuple[str, int] | None:
        """Pop the next URL from the BFS frontier (FIFO). Returns (url, depth) or None."""
        url = await self._redis.lpop(self._frontier_key)
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
        return await self._redis.llen(self._frontier_key)

    async def add_to_frontier(self, urls: list[str], depth: int):
        """Add discovered URLs to the BFS frontier (FIFO, no scoring).

        Uses a companion SET (queued_key) for O(1) dedup so the same
        normalized URL is never pushed twice into the LIST.
        """
        from app.services.dedup import normalize_url

        for url in urls:
            norm = normalize_url(url)
            # O(1) dedup via queued SET — skip if already enqueued
            if await self._redis.sismember(self._queued_key, norm):
                continue
            if await self.is_visited(norm):
                continue
            if not self._should_crawl(url, depth):
                continue
            if self.config.respect_robots_txt and not await self._is_allowed_by_robots(
                url
            ):
                continue

            visited_count = await self.get_visited_count()
            frontier_size = await self.get_frontier_size()
            if visited_count + frontier_size >= self.config.max_pages * 5:
                break

            await self._redis.rpush(self._frontier_key, norm)
            await self._redis.sadd(self._queued_key, norm)
            await self._redis.hset(self._depth_key, norm, depth)

    # Paths that never have useful content — utility/chrome pages
    _JUNK_PATH_SEGMENTS = {
        "signin", "sign-in", "sign_in", "login", "log-in", "log_in",
        "signup", "sign-up", "sign_up", "register", "registration",
        "cart", "checkout", "basket", "bag", "payment", "order",
        "account", "my-account", "myaccount", "profile", "settings",
        "wishlist", "wish-list", "favorites", "favourites", "saved",
        "help", "contact", "contact-us", "support", "faq", "faqs",
        "privacy", "privacy-policy", "terms", "terms-of-service",
        "terms-of-use", "legal", "disclaimer", "cookie-policy",
        "language", "locale", "region", "country-selector",
        "subscribe", "unsubscribe", "newsletter",
        "compare", "comparison",
        "returns", "return-policy", "refund", "shipping",
        "sitemap", "sitemap.xml",
        "feed", "rss", "atom",
        "print", "share", "email-friend",
        "404", "error", "not-found",
    }

    def _should_crawl(self, url: str, depth: int) -> bool:
        """Check if a URL should be crawled based on config filters."""
        parsed = urlparse(url)

        # Check depth
        if depth > self.config.max_depth:
            return False

        # Check domain (unless external links allowed)
        # Strip www. from both sides so www.example.com == example.com
        if not self.config.allow_external_links and self._strip_www(parsed.netloc) != self._base_domain_norm:
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

        # Skip utility/chrome pages (sign in, cart, account, etc.)
        # Check ALL path segments — catches /en/cart/, /user/login/, etc.
        path_segments = [s.lower() for s in parsed.path.strip("/").split("/") if s]
        if any(seg in self._JUNK_PATH_SEGMENTS for seg in path_segments):
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

    async def take_screenshot(self, url: str, raw_html: str) -> str | None:
        """Take a screenshot using the crawl session browser.

        Renders the raw HTML in a browser page with a <base> tag so relative
        resources resolve.  Returns base64-encoded JPEG or None on failure.
        """
        import base64
        import re as _re

        if not self._crawl_session:
            return None
        page = None
        try:
            page = await self._crawl_session.new_page()
            # Inject <base> so images/CSS with relative URLs load from the site
            html = _re.sub(
                r"(<head[^>]*>)",
                rf'\1<base href="{url}">',
                raw_html,
                count=1,
                flags=_re.IGNORECASE,
            )
            await page.set_content(html, wait_until="domcontentloaded")
            await page.wait_for_timeout(500)
            ss_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=True
            )
            return base64.b64encode(ss_bytes).decode()
        except Exception as e:
            logger.debug(f"Screenshot failed for {url}: {e}")
            return None
        finally:
            if page:
                try:
                    await self._crawl_session.close_page(page)
                except Exception:
                    pass

    async def fetch_page_only(
        self,
        url: str,
        pinned_strategy: str | None = None,
        pinned_tier: int | None = None,
    ) -> dict | None:
        """Fetch-only phase for pipeline mode — returns raw data without extraction.

        Lets the tier escalation system decide what works best:
        - Sites like Amazon: cookie_http (tier 0) works, browsers get blocked
        - JS-heavy SPAs: HTTP tiers fail → naturally escalates to browser
        The crawl_session is still passed for browser-tier racing.
        """
        opts = self.config.scrape_options or ScrapeOptions()
        # Exclude "screenshot" so needs_browser=False → fast HTTP tiers can run.
        # Screenshots are captured separately by the crawl worker consumer.
        formats = list((set(opts.formats) | {"links"}) - {"screenshot"})

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
            pinned_strategy=pinned_strategy,
            pinned_tier=pinned_tier,
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
                self._frontier_key, self._queued_key, self._visited_key, self._depth_key
            )
            await self._redis.aclose()
            self._redis = None
