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

# ---------------------------------------------------------------------------
# URL priority scoring — content-rich pages (products, articles) rank higher
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[a-z0-9]+-[a-z0-9]+-[a-z0-9]+")  # word-word-word slugs
_ALNUM_ID_RE = re.compile(r"^[A-Z0-9]{6,}$")  # e.g. B09V3KXJPB (ASIN)
_NUMERIC_ID_RE = re.compile(r"^\d{4,}$")  # numeric product/article IDs
_DATE_RE = re.compile(r"\d{4}[/-]\d{2}")  # date patterns in path (blog posts)


def score_url(url: str) -> float:
    """Score a URL for crawl priority.  Higher = crawled sooner.

    Heuristics (additive):
      +3  slug-like path segment (word-word-word) → likely product/article
      +2  alphanumeric ID segment (≥6 chars)      → likely product detail
      +2  numeric ID segment (≥4 digits)           → likely item page
      +1  date pattern in path                     → likely blog post
      -1  per path segment beyond 2                → penalise deep nav
      -1  per query parameter                      → penalise filter pages
      -2  segment > 40 chars                       → penalise hash/noise
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.strip("/").split("/") if s]
    score = 10.0  # base score

    for seg in segments:
        if _SLUG_RE.search(seg):
            score += 3
        if _ALNUM_ID_RE.match(seg):
            score += 2
        if _NUMERIC_ID_RE.match(seg):
            score += 2
        if len(seg) > 40:
            score -= 2

    if _DATE_RE.search(parsed.path):
        score += 1

    # Penalise deep paths
    if len(segments) > 2:
        score -= (len(segments) - 2)

    # Penalise query-heavy URLs
    if parsed.query:
        params = parsed.query.count("&") + 1
        score -= params

    return max(score, 0.0)


class WebCrawler:
    """Priority web crawler with Redis-backed ZSET frontier and visited set.

    The frontier uses a Redis sorted set (ZADD/ZPOPMAX) so that
    content-rich pages (products, articles) are crawled before
    navigation / category pages.
    """

    def __init__(self, job_id: str, config: CrawlRequest, proxy_manager=None):
        self.job_id = job_id
        self.config = config
        self.base_url = config.url
        self.base_domain = urlparse(config.url).netloc
        self._robots_cache: dict[str, RobotExclusionRulesParser] = {}
        self._redis: aioredis.Redis | None = None
        self._proxy_manager = proxy_manager
        self._crawl_session = None
        self.detected_doc_framework: str | None = None  # Set by JS discovery

        # Redis keys for this crawl
        self._frontier_key = f"crawl:{job_id}:frontier"
        self._visited_key = f"crawl:{job_id}:visited"
        self._depth_key = f"crawl:{job_id}:depth"

    async def initialize(self):
        """Set up Redis connection, initial frontier, and persistent browser session.

        For documentation sites (GitBook, Docusaurus, MkDocs, etc.), the frontier
        is pre-seeded with URLs discovered via deep JS navigation discovery. This
        is critical because doc sites render their navigation via JavaScript — a
        normal HTTP fetch of the start page yields almost no internal links, so BFS
        stalls after 1-2 pages.
        """
        # Create a fresh Redis connection for this crawl task
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

        # Seed the frontier with the start URL (highest priority)
        start_score = score_url(self.base_url) + 100  # boost start URL
        await self._redis.zadd(self._frontier_key, {self.base_url: start_score})
        await self._redis.hset(self._depth_key, self.base_url, 0)
        # Set TTL on all keys (24 hours)
        for key in [self._frontier_key, self._visited_key, self._depth_key]:
            await self._redis.expire(key, 86400)

        # Deep JS Navigation Discovery: pre-seed frontier for doc sites
        # Uses headless browser to render the start page, detect the doc framework,
        # expand all sidebar nav sections, and extract every navigation link.
        await self._seed_frontier_with_js_discovery()

        # Create persistent browser session for this crawl
        from app.services.browser import CrawlSession, browser_pool

        self._crawl_session = CrawlSession(browser_pool)
        proxy = None
        if self._proxy_manager:
            proxy_obj = self._proxy_manager.get_random()
            if proxy_obj:
                proxy = self._proxy_manager.to_playwright(proxy_obj)
        await self._crawl_session.start(proxy=proxy, target_url=self.base_url)

    async def _seed_frontier_with_js_discovery(self):
        """Pre-seed the crawl frontier using deep JS navigation discovery.

        This runs a headless browser against the start URL, detects if it's a
        documentation site, expands all collapsible sidebar sections, and extracts
        every navigation link. The discovered URLs are added to the frontier so
        the BFS crawler has a rich set of pages to visit — even if individual page
        scrapes (via HTTP) don't find sidebar links.
        """
        try:
            from app.services.mapper import (
                _deep_discover_via_stealth_engine,
                _deep_discover_via_local_browser,
            )

            # Try stealth engine first (best anti-detection)
            html, discovered_links, doc_framework = await _deep_discover_via_stealth_engine(
                self.base_url
            )
            if not discovered_links:
                # Fallback to local browser
                html, discovered_links = await _deep_discover_via_local_browser(
                    self.base_url
                )

            if not discovered_links:
                logger.debug(f"No JS nav links discovered for {self.base_url}")
                return

            # Store detected framework so the crawl worker can pin browser strategy
            if doc_framework:
                self.detected_doc_framework = doc_framework

            logger.info(
                f"Deep JS discovery found {len(discovered_links)} URLs for {self.base_url}"
                f"{f' (framework: {doc_framework})' if doc_framework else ''}"
            )

            # Filter and add to frontier with priority scoring
            from app.services.dedup import normalize_url

            added = 0
            for link_url in discovered_links:
                if added >= self.config.max_pages * 5:
                    break
                norm = normalize_url(link_url)
                if await self.is_visited(norm):
                    continue
                if not self._should_crawl(link_url, depth=1):
                    continue

                url_score = score_url(link_url)
                await self._redis.zadd(self._frontier_key, {link_url: url_score})
                await self._redis.hset(self._depth_key, link_url, 1)
                added += 1

            logger.info(
                f"Pre-seeded crawl frontier with {added} URLs from JS discovery"
            )
        except Exception as e:
            logger.warning(f"JS nav discovery during crawl init failed: {e}")
            # Non-fatal — BFS will still work via normal link extraction

    async def get_next_url(self) -> tuple[str, int] | None:
        """Pop the highest-priority URL from the frontier. Returns (url, depth) or None."""
        result = await self._redis.zpopmax(self._frontier_key, count=1)
        if not result:
            return None
        url, _score = result[0]
        depth = await self._redis.hget(self._depth_key, url)
        return url, int(depth or 0)

    async def mark_visited(self, url: str):
        await self._redis.sadd(self._visited_key, url)

    async def is_visited(self, url: str) -> bool:
        return await self._redis.sismember(self._visited_key, url)

    async def get_visited_count(self) -> int:
        return await self._redis.scard(self._visited_key)

    async def get_frontier_size(self) -> int:
        return await self._redis.zcard(self._frontier_key)

    async def add_to_frontier(self, urls: list[str], depth: int):
        """Add discovered URLs to the priority frontier (scored by content likelihood)."""
        from app.services.dedup import normalize_url

        for url in urls:
            norm = normalize_url(url)
            # ZSET handles dedup implicitly (same member = update score)
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

            url_score = score_url(url) - depth  # penalise deeper pages
            await self._redis.zadd(self._frontier_key, {url: url_score})
            await self._redis.hset(self._depth_key, url, depth)

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

        # Skip utility/chrome pages (sign in, cart, account, etc.)
        path_segments = [s.lower() for s in parsed.path.strip("/").split("/") if s]
        if path_segments and path_segments[0] in self._JUNK_PATH_SEGMENTS:
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
        """Fetch-only phase for pipeline mode — returns raw data without extraction."""
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
                self._frontier_key, self._visited_key, self._depth_key
            )
            await self._redis.aclose()
            self._redis = None
