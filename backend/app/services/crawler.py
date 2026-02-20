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
# URL content-richness scorer (completely generic, no site-specific patterns)
# ---------------------------------------------------------------------------

# Regex patterns for structural analysis
_SLUG_RE = re.compile(r"[a-z0-9]+-[a-z0-9]+-[a-z0-9]+")  # 3+ hyphenated words
_ALNUM_ID_RE = re.compile(r"^[A-Z0-9]{6,}$")              # product/article ID
_NUMERIC_ID_RE = re.compile(r"^\d{4,}$")                   # numeric ID
_DATE_RE = re.compile(r"\d{4}[/-]\d{2}")                   # date in path


def score_url(url: str) -> float:
    """Score a URL by predicted content richness.  Higher = more likely useful.

    Uses only structural URL signals — works on any website:
    - Path depth (content lives 2-4 levels deep)
    - Slug detection (hyphenated-word segments = articles/products)
    - ID detection (alphanumeric codes = specific items)
    - Date detection (blog/news articles)
    - Query complexity penalty (tracking params = navigation junk)
    - Path segment length (longer segments = more descriptive = more content)
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = [s for s in path.split("/") if s]
    score = 5.0  # base

    depth = len(segments)
    if depth == 0:
        score += 3  # homepage — usually content-rich
    elif depth == 1:
        # Single segment: could be a category or a page.
        # Short single segments are usually nav ("/b", "/s", "/gp").
        if len(segments[0]) > 15:
            score += 1  # long slug = likely content
        else:
            score -= 2  # short = likely nav/category
    elif 2 <= depth <= 4:
        score += 3  # sweet spot for content pages
    elif depth > 6:
        score -= 1  # excessively deep, often pagination/filters

    # Slug detection: hyphenated multi-word segments signal content slugs
    # e.g. "cetaphil-hydrating-sulphate-free-niacinamide"
    has_slug = False
    for seg in segments:
        if _SLUG_RE.search(seg.lower()) and len(seg) > 15:
            score += 5
            has_slug = True
            break

    # ID detection: alphanumeric codes signal specific items
    for seg in segments:
        if _ALNUM_ID_RE.match(seg):
            score += 4
            break
        if _NUMERIC_ID_RE.match(seg):
            score += 3
            break

    # Date in path: articles/blog posts
    if _DATE_RE.search(path):
        score += 3

    # Average segment length — longer descriptive paths = richer content
    if segments:
        avg_len = sum(len(s) for s in segments) / len(segments)
        if avg_len > 20:
            score += 2
        elif avg_len < 4:
            score -= 2  # tiny segments like "/b/", "/s/", "/gp/"

    # Query parameter penalty — lots of params = tracking/filter URLs
    query = parsed.query
    if query:
        param_count = query.count("&") + 1
        if param_count > 8:
            score -= 4
        elif param_count > 4:
            score -= 2

    # Pages without slugs or IDs at depth > 1 are likely nav/browse pages
    if depth >= 1 and not has_slug:
        all_short = all(len(s) < 10 for s in segments)
        if all_short:
            score -= 3

    return max(0.0, score)


class WebCrawler:
    """BFS web crawler with Redis-backed priority frontier and visited set.

    The frontier uses a Redis sorted set (ZSET) scored by predicted content
    richness so the crawler fetches the most promising URLs first.
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

        # Seed the frontier with the start URL (highest priority)
        start_score = score_url(self.base_url) + 10  # bonus for seed URL
        await self._redis.zadd(self._frontier_key, {self.base_url: start_score})
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
        """Pop the highest-scored URL from the frontier. Returns (url, depth) or None."""
        # ZPOPMAX returns [(member, score)] — highest score first
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
        """Add discovered URLs to the priority frontier after filtering."""
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
            if visited_count + frontier_size >= self.config.max_pages * 3:
                # Allow 3x headroom so we can be selective
                break

            url_score = score_url(url)
            # Slight depth penalty: prefer shallower pages when scores are equal
            url_score -= depth * 0.5
            await self._redis.zadd(self._frontier_key, {url: max(0, url_score)})
            await self._redis.hset(self._depth_key, url, depth)

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

        if not self._crawl_session:
            return None
        page = None
        try:
            page = await self._crawl_session.new_page()
            # Inject <base> so images/CSS with relative URLs load from the site
            html = raw_html
            if "<head" in html.lower():
                html = html.replace("<head>", f'<head><base href="{url}">', 1)
                if "<head>" not in raw_html:
                    # Handle <head ...attrs>
                    import re as _re

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

    async def fetch_page_only(self, url: str) -> dict | None:
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
