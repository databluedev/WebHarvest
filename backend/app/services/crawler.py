import fnmatch
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from robotexclusionrulesparser import RobotExclusionRulesParser

from app.schemas.crawl import CrawlRequest, ScrapeOptions
from app.schemas.scrape import ScrapeRequest
from app.services.scraper import scrape_url, scrape_url_fetch_only

logger = logging.getLogger(__name__)

# Junk path segments — skip admin panels, auth flows, shopping carts, feeds.
# Only EXACT path segments are matched (not substrings), so
# "/admin-guide/quickstart" is allowed while "/admin/dashboard" is blocked.
_JUNK_PATH_SEGMENTS = {
    "wp-admin",
    "wp-login",
    "wp-json",
    "admin",
    "login",
    "logout",
    "signup",
    "register",
    "cart",
    "checkout",
    "account",
    "password",
    "feed",
    "rss",
    "xmlrpc",
    "cgi-bin",
}

# Redis key TTL for crawl state (2 hours — covers long crawls)
_REDIS_TTL = 7200


class WebCrawler:
    """Web crawler with Redis-backed frontier for distributed Celery architecture.

    Supports BFS, DFS, and Best-First traversal backed by Redis data structures:
    - BFS = Redis LIST (RPUSH/LPOP) — queue behavior
    - DFS = Redis LIST (LPUSH/LPOP) — stack behavior
    - BFF = Redis ZSET (ZADD/ZPOPMIN) — scored priority queue

    Falls back to in-memory deep_crawl strategies when Redis is unavailable
    (CLI mode / local development).
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
        self._base_domain_norm = self._strip_www(self.base_domain)
        self._robots_cache: dict[str, RobotExclusionRulesParser] = {}
        self._crawl_delay_cache: dict[str, float | None] = {}
        self._proxy_manager = proxy_manager
        self._crawl_session = None
        self._use_redis = False
        self._redis = None
        self._strategy = None  # In-memory fallback

        # Redis key prefixes for this job
        self._key_frontier = f"crawl:{job_id}:frontier"
        self._key_visited = f"crawl:{job_id}:visited"
        self._key_depth = f"crawl:{job_id}:depth"

        self._crawl_strategy = getattr(config, "crawl_strategy", "bfs")

    async def initialize(self):
        """Set up Redis frontier (or fallback), seed URLs, start browser session."""
        from app.services.dedup import normalize_url

        # Try to use Redis for distributed frontier
        try:
            from app.core.redis import redis_client
            await redis_client.ping()
            self._redis = redis_client
            self._use_redis = True
            logger.info(f"Crawl {self.job_id}: using Redis-backed frontier ({self._crawl_strategy})")
        except Exception as e:
            logger.warning(f"Crawl {self.job_id}: Redis unavailable ({e}), using in-memory frontier")
            self._use_redis = False
            self._init_memory_strategy()

        # Seed the start URL
        norm_start = normalize_url(self.base_url)
        if self._use_redis:
            await self._redis_add_urls([(norm_start, 0)])
        else:
            self._strategy.seed(self.base_url)

        # Sitemap-first seeding
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

    def _init_memory_strategy(self):
        """Initialize in-memory fallback strategy (CLI mode)."""
        from app.services.deep_crawl.strategies import BFSStrategy, DFSStrategy, BestFirstStrategy

        strategy_kwargs = {
            "max_depth": self.config.max_depth,
            "max_pages": self.config.max_pages,
            "include_external": self.config.allow_external_links,
        }
        if self._crawl_strategy == "dfs":
            self._strategy = DFSStrategy(**strategy_kwargs)
        elif self._crawl_strategy == "bff":
            self._strategy = BestFirstStrategy(**strategy_kwargs)
        else:
            self._strategy = BFSStrategy(**strategy_kwargs)

    # ------------------------------------------------------------------
    # Redis frontier operations
    # ------------------------------------------------------------------

    async def _redis_add_urls(self, url_depth_pairs: list[tuple[str, int]]):
        """Add URLs to Redis frontier with their depths."""
        if not url_depth_pairs:
            return
        pipe = self._redis.pipeline()
        for url, depth in url_depth_pairs:
            if self._crawl_strategy == "bfs":
                # Queue: RPUSH for FIFO
                pipe.rpush(self._key_frontier, json.dumps({"url": url, "depth": depth}))
            elif self._crawl_strategy == "dfs":
                # Stack: LPUSH for LIFO
                pipe.lpush(self._key_frontier, json.dumps({"url": url, "depth": depth}))
            elif self._crawl_strategy == "bff":
                # Priority queue: score = depth (lower depth = higher priority)
                pipe.zadd(self._key_frontier, {json.dumps({"url": url, "depth": depth}): depth})
            # Store depth mapping
            pipe.hset(self._key_depth, url, depth)
        # Set TTL on all keys
        pipe.expire(self._key_frontier, _REDIS_TTL)
        pipe.expire(self._key_depth, _REDIS_TTL)
        pipe.expire(self._key_visited, _REDIS_TTL)
        await pipe.execute()

    async def _redis_pop_url(self) -> tuple[str, int] | None:
        """Pop next URL from Redis frontier."""
        if self._crawl_strategy == "bff":
            # ZPOPMIN returns [(member, score)] or empty list
            result = await self._redis.zpopmin(self._key_frontier, count=1)
            if not result:
                return None
            member, _score = result[0]
            data = json.loads(member)
            return data["url"], data["depth"]
        else:
            # LPOP for both BFS (RPUSH+LPOP=queue) and DFS (LPUSH+LPOP=stack)
            raw = await self._redis.lpop(self._key_frontier)
            if not raw:
                return None
            data = json.loads(raw)
            return data["url"], data["depth"]

    async def _redis_frontier_size(self) -> int:
        """Get current frontier size from Redis."""
        if self._crawl_strategy == "bff":
            return await self._redis.zcard(self._key_frontier)
        else:
            return await self._redis.llen(self._key_frontier)

    # ------------------------------------------------------------------
    # Public API (used by crawl_worker)
    # ------------------------------------------------------------------

    async def _seed_from_sitemaps(self):
        """Seed the crawl frontier from sitemap.xml."""
        try:
            from app.services.mapper import _parse_sitemaps
            from app.services.dedup import normalize_url_for_crawl

            sitemap_links = await _parse_sitemaps(self.base_url)
            if not sitemap_links:
                logger.debug(f"No sitemap URLs found for {self.base_url}")
                return

            added = 0
            max_seed = self.config.max_pages * 5
            seed_pairs = []
            for link in sitemap_links:
                if added >= max_seed:
                    break
                url = link.url
                norm = normalize_url_for_crawl(url)
                if self._use_redis:
                    if await self._redis.sismember(self._key_visited, norm):
                        continue
                else:
                    if norm in self._visited:
                        continue
                if not self._should_crawl(url, depth=1):
                    continue
                seed_pairs.append((norm, 1))
                added += 1

            if seed_pairs:
                if self._use_redis:
                    await self._redis_add_urls(seed_pairs)
                else:
                    await self._strategy.add_discovered_urls(
                        [u for u, _ in seed_pairs], self.base_url, 1
                    )
                logger.info(
                    f"Sitemap seeding: added {added} URLs from "
                    f"{len(sitemap_links)} sitemap entries for {self.base_url}"
                )
        except Exception as e:
            logger.warning(f"Sitemap seeding failed for {self.base_url}: {e}")

    async def get_next_url(self) -> tuple[str, int] | None:
        """Get next URL from the frontier."""
        if self._use_redis:
            return await self._redis_pop_url()

        # In-memory fallback
        batch = await self._strategy.get_next_urls()
        if not batch:
            return None
        item = batch[0]
        if len(batch) > 1:
            for extra in batch[1:]:
                await self._strategy.add_discovered_urls(
                    [extra.url], extra.parent_url or self.base_url, extra.depth
                )
        return item.url, item.depth

    async def mark_visited(self, url: str):
        if self._use_redis:
            await self._redis.sadd(self._key_visited, url)
            await self._redis.expire(self._key_visited, _REDIS_TTL)
        else:
            self._visited.add(url)
            self._strategy._state.visited.add(url)
            self._strategy._state.pages_crawled += 1

    async def is_visited(self, url: str) -> bool:
        if self._use_redis:
            return bool(await self._redis.sismember(self._key_visited, url))
        return url in self._visited

    async def get_visited_count(self) -> int:
        if self._use_redis:
            return await self._redis.scard(self._key_visited)
        return len(self._visited)

    async def get_frontier_size(self) -> int:
        if self._use_redis:
            return await self._redis_frontier_size()
        if hasattr(self._strategy, '_queue'):
            return len(self._strategy._queue)
        elif hasattr(self._strategy, '_stack'):
            return len(self._strategy._stack)
        elif hasattr(self._strategy, '_pqueue'):
            return len(self._strategy._pqueue)
        return 0

    async def add_to_frontier(self, urls: list[str], depth: int):
        """Add discovered URLs to frontier with filtering and backpressure."""
        from app.services.dedup import normalize_url

        # Backpressure check — cap frontier size
        visited_count = await self.get_visited_count()
        frontier_size = await self.get_frontier_size()
        frontier_cap = self.config.max_pages * 20

        if visited_count + frontier_size >= frontier_cap:
            logger.info(
                f"Backpressure: frontier full ({visited_count} visited + "
                f"{frontier_size} queued >= {frontier_cap} cap), "
                f"dropping {len(urls)} discovered URLs for {self.job_id}"
            )
            return

        # Faceted URL filtering
        _pre_facet = len(urls)
        if getattr(self.config, "filter_faceted_urls", True):
            from app.services.dedup import filter_faceted_urls
            urls = filter_faceted_urls(urls)

        filtered = []
        _rejected_visited = 0
        _rejected_crawl = 0
        _rejected_robots = 0
        for url in urls:
            norm = normalize_url(url)
            if await self.is_visited(norm):
                _rejected_visited += 1
                continue
            if not self._should_crawl(url, depth):
                _rejected_crawl += 1
                continue
            if self.config.respect_robots_txt and not await self._is_allowed_by_robots(url):
                _rejected_robots += 1
                continue

            # Re-check backpressure after each URL
            current_total = visited_count + frontier_size + len(filtered)
            if current_total >= frontier_cap:
                logger.info(
                    f"Backpressure: frontier cap reached mid-batch, "
                    f"added {len(filtered)}/{len(urls)} URLs for {self.job_id}"
                )
                break
            filtered.append((norm, depth))

        if not filtered:
            logger.warning(
                f"Frontier filter: 0/{_pre_facet} URLs survived for {self.job_id} "
                f"(after_facet={len(urls)}, visited={_rejected_visited}, "
                f"crawl_filter={_rejected_crawl}, robots={_rejected_robots})"
            )
            return
        logger.info(
            f"Frontier: added {len(filtered)}/{_pre_facet} URLs for {self.job_id} "
            f"(facet={_pre_facet - len(urls)}, visited={_rejected_visited}, "
            f"crawl_filter={_rejected_crawl}, robots={_rejected_robots})"
        )

        if self._use_redis:
            await self._redis_add_urls(filtered)
        else:
            await self._strategy.add_discovered_urls(
                [u for u, _ in filtered], self.base_url, depth
            )

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

        # Skip junk path segments (admin, login, cart, etc.)
        # Set membership = exact segment match: "/admin" blocked, "/admin-guide" allowed
        path_parts = [p.lower() for p in parsed.path.split("/") if p]
        if any(part in _JUNK_PATH_SEGMENTS for part in path_parts):
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

            # Cache Crawl-Delay directive (polite scraping)
            try:
                delay = parser.get_crawl_delay("*")
                if delay is not None:
                    # Cap at 30s to avoid absurdly slow crawls
                    self._crawl_delay_cache[domain] = min(float(delay), 30.0)
                    logger.info(
                        "Respecting Crawl-Delay: %.1fs for %s", delay, domain
                    )
            except Exception:
                pass

        return self._robots_cache[domain].is_allowed("*", url)

    def get_crawl_delay(self, url: str) -> float | None:
        """Return the Crawl-Delay (seconds) from robots.txt for a URL's domain.

        Returns None if no Crawl-Delay was specified. The value is cached
        after the first robots.txt fetch for each domain.
        """
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        return self._crawl_delay_cache.get(domain)

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
        """Take a screenshot by navigating to the URL in the crawl session.

        Uses page.goto() so images, CSS, and lazy-loaded content render
        properly (set_content doesn't load external resources reliably).
        Returns base64-encoded JPEG or None on failure.
        """
        import base64

        if not self._crawl_session:
            return None
        page = None
        try:
            page = await self._crawl_session.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            ss_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=False
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
            # Transfer cookies from winning strategy into persistent session
            ws = fetch_result.get("winning_strategy", "")
            if ws and ws != "crawl_session" and self._crawl_session:
                try:
                    await self._crawl_session.sync_cookies_from_pool(url)
                except Exception:
                    pass
        return fetch_result

    def export_state(self) -> dict:
        """Export crawl state for checkpoint/resume.

        For Redis mode, serializes Redis state to JSON.
        For in-memory mode, delegates to strategy.
        """
        if not self._use_redis and self._strategy:
            return self._strategy.export_state()
        # Redis mode: state is already persisted in Redis
        return {
            "job_id": self.job_id,
            "strategy": self._crawl_strategy,
            "use_redis": True,
            "redis_keys": {
                "frontier": self._key_frontier,
                "visited": self._key_visited,
                "depth": self._key_depth,
            },
        }

    def restore_state(self, state_data: dict):
        """Restore crawl state from checkpoint."""
        if not self._use_redis and self._strategy:
            self._strategy.restore_state(state_data)
            self._visited = self._strategy._state.visited.copy()

    async def cleanup(self):
        """Close browser session and clean up Redis keys."""
        if self._crawl_session:
            try:
                await self._crawl_session.stop()
            except Exception:
                pass
            self._crawl_session = None

        # Clean up Redis keys for this job
        if self._use_redis and self._redis:
            try:
                await self._redis.delete(
                    self._key_frontier,
                    self._key_visited,
                    self._key_depth,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # In-memory fallback support
    # ------------------------------------------------------------------

    @property
    def _visited(self) -> set[str]:
        """In-memory visited set (only used in non-Redis mode)."""
        if not hasattr(self, "_visited_set"):
            self._visited_set: set[str] = set()
        return self._visited_set

    @_visited.setter
    def _visited(self, value: set[str]):
        self._visited_set = value
