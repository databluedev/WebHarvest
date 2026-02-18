import base64
import logging
import random
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas.scrape import ScrapeRequest, ScrapeData, PageMetadata
from app.services.browser import browser_pool
from app.services.content import (
    extract_main_content,
    apply_tag_filters,
    html_to_markdown,
    extract_links,
    extract_links_detailed,
    extract_metadata,
    extract_structured_data,
    extract_headings,
    extract_images,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anti-bot detection patterns
# ---------------------------------------------------------------------------

_BLOCK_PATTERNS = [
    "javascript is disabled",
    "enable javascript",
    "requires javascript",
    "javascript is required",
    "please enable javascript",
    "you need to enable javascript",
    "this page requires javascript",
    "turn on javascript",
    "activate javascript",
    "captcha",
    "verify you are human",
    "verify you're human",
    "are you a robot",
    "not a robot",
    "bot detection",
    "access denied",
    "please verify",
    "unusual traffic",
    "automated access",
    "checking your browser",
    "just a moment",
    "attention required",
    "please wait while we verify",
    "ray id",
    "performance & security by cloudflare",
    "sucuri website firewall",
    "pardon our interruption",
    "press & hold",
    "blocked by",
    "we need to verify that you're not a robot",
    "sorry, we just need to make sure",
    "one more step",
]

_HARD_SITES = {
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.co.jp",
    "amazon.in", "amazon.ca", "amazon.com.au", "amazon.es", "amazon.it",
    "google.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "zillow.com", "indeed.com", "glassdoor.com",
    "walmart.com", "target.com", "bestbuy.com", "ebay.com",
    "cloudflare.com", "netflix.com", "spotify.com",
    "ticketmaster.com", "stubhub.com",
    "nike.com", "adidas.com",
    "booking.com", "airbnb.com", "expedia.com",
    "craigslist.org", "yelp.com",
}

_HTTPX_HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
]

_GOOGLE_REFERRERS = [
    "https://www.google.com/",
    "https://www.google.com/search?q=",
    "https://www.google.co.uk/",
]


def _is_hard_site(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return any(domain == d or domain.endswith("." + d) for d in _HARD_SITES)
    except Exception:
        return False


def _looks_blocked(html: str) -> bool:
    if not html:
        return True

    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body_html = body_match.group(1) if body_match else html
    body_text = re.sub(r"<[^>]+>", " ", body_html).strip().lower()

    if len(body_text) < 1500:
        for pattern in _BLOCK_PATTERNS:
            if pattern in body_text:
                return True

    head = html[:5000].lower()
    for pattern in ["javascript is disabled", "enable javascript", "access denied",
                    "attention required", "just a moment", "checking your browser",
                    "captcha", "robot", "verify you are human", "not a robot"]:
        if pattern in head:
            return True

    if len(body_text) < 300 and ("<noscript" in html.lower() or "captcha" in html.lower()):
        return True

    return False


# ---------------------------------------------------------------------------
# Main scrape
# ---------------------------------------------------------------------------

async def scrape_url(
    request: ScrapeRequest,
    proxy_manager=None,
) -> ScrapeData:
    """
    Scrape a URL with maximum anti-detection.

    Pipeline:
    1. curl_cffi with Chrome TLS impersonation (ALL sites including hard sites)
    2. httpx HTTP/2 fallback (non-hard sites only)
    3. Chromium browser with stealth + warm-up navigation
    4. Firefox browser if available (different engine/TLS)
    5. Chromium aggressive: human simulation + challenge wait loop
    """
    from app.core.cache import get_cached_scrape, set_cached_scrape
    from app.core.metrics import scrape_duration_seconds

    url = request.url
    start_time = time.time()

    use_cache = not request.actions and "screenshot" not in request.formats and not request.extract
    if use_cache:
        cached = await get_cached_scrape(url, request.formats)
        if cached:
            try:
                return ScrapeData(**cached)
            except Exception:
                pass

    raw_html = ""
    status_code = 0
    screenshot_b64 = None
    action_screenshots = []
    response_headers: dict[str, str] = {}
    raw_html_best = ""

    proxy_url = None
    proxy_playwright = None
    if proxy_manager:
        proxy_obj = proxy_manager.get_random()
        if proxy_obj:
            proxy_url = proxy_manager.to_httpx(proxy_obj)
            proxy_playwright = proxy_manager.to_playwright(proxy_obj)

    hard_site = _is_hard_site(url)
    needs_browser = bool(
        request.actions
        or "screenshot" in request.formats
        or request.wait_for > 0
    )

    fetched = False

    # === Strategy 1: curl_cffi with Chrome TLS fingerprint (ALL sites) ===
    if not needs_browser:
        try:
            raw_html, status_code, response_headers = await _fetch_with_curl_cffi(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and status_code < 400 and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"curl_cffi succeeded for {url}")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
                logger.info(f"curl_cffi blocked for {url}, escalating")
        except Exception as e:
            logger.debug(f"curl_cffi failed for {url}: {e}")

    # === Strategy 1b: httpx HTTP/2 (non-hard sites only) ===
    if not fetched and not needs_browser and not hard_site:
        try:
            raw_html, status_code, response_headers = await _fetch_with_httpx(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and status_code < 400 and not _looks_blocked(raw_html):
                fetched = True
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.debug(f"httpx failed for {url}: {e}")

    # === Strategy 2: Chromium browser with stealth + warm-up ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_stealth(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Chromium stealth succeeded for {url}")
            else:
                logger.info(f"Chromium stealth blocked for {url}")
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Chromium stealth failed for {url}: {e}")

    # === Strategy 3: Firefox browser (different TLS fingerprint) ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, use_firefox=True)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Firefox succeeded for {url}")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Firefox failed for {url}: {e}")

    # === Strategy 4: Chromium aggressive — human simulation + challenge wait ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_aggressive(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Aggressive browser succeeded for {url}")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                if not raw_html:
                    raw_html = raw_html_best
                logger.warning(f"All strategies exhausted for {url}, using best result")
        except Exception as e:
            logger.warning(f"Aggressive browser failed for {url}: {e}")
            if not raw_html:
                raw_html = raw_html_best

    if not raw_html:
        duration = time.time() - start_time
        scrape_duration_seconds.observe(duration)
        return ScrapeData(
            metadata=PageMetadata(source_url=url, status_code=status_code or 0),
        )

    # === Content extraction ===
    result_data: dict[str, Any] = {}

    clean_html = extract_main_content(raw_html, url) if request.only_main_content else raw_html
    if request.include_tags or request.exclude_tags:
        clean_html = apply_tag_filters(clean_html, request.include_tags, request.exclude_tags)

    if "markdown" in request.formats:
        result_data["markdown"] = html_to_markdown(clean_html)
    if "html" in request.formats:
        result_data["html"] = clean_html
    if "raw_html" in request.formats:
        result_data["raw_html"] = raw_html
    if "links" in request.formats:
        result_data["links"] = extract_links(raw_html, url)
        result_data["links_detail"] = extract_links_detailed(raw_html, url)
    if "screenshot" in request.formats:
        if screenshot_b64:
            result_data["screenshot"] = screenshot_b64
        elif action_screenshots:
            result_data["screenshot"] = action_screenshots[-1]
    if "structured_data" in request.formats:
        result_data["structured_data"] = extract_structured_data(raw_html)
    if "headings" in request.formats:
        result_data["headings"] = extract_headings(raw_html)
    if "images" in request.formats:
        result_data["images"] = extract_images(raw_html, url)

    metadata_dict = extract_metadata(raw_html, url, status_code, response_headers)
    metadata = PageMetadata(**metadata_dict)

    scrape_data = ScrapeData(
        markdown=result_data.get("markdown"),
        html=result_data.get("html"),
        raw_html=result_data.get("raw_html"),
        links=result_data.get("links"),
        links_detail=result_data.get("links_detail"),
        screenshot=result_data.get("screenshot"),
        structured_data=result_data.get("structured_data"),
        headings=result_data.get("headings"),
        images=result_data.get("images"),
        metadata=metadata,
    )

    if use_cache and fetched:
        try:
            await set_cached_scrape(url, request.formats, scrape_data.model_dump())
        except Exception:
            pass

    duration = time.time() - start_time
    scrape_duration_seconds.observe(duration)
    return scrape_data


# ---------------------------------------------------------------------------
# Strategy: curl_cffi — Chrome TLS fingerprint impersonation
# ---------------------------------------------------------------------------

async def _fetch_with_curl_cffi(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    """HTTP fetch with curl_cffi impersonating Chrome's exact TLS/JA3/HTTP2 fingerprint."""
    from curl_cffi.requests import AsyncSession

    timeout_seconds = timeout / 1000
    async with AsyncSession(impersonate="chrome124") as session:
        kwargs: dict[str, Any] = dict(
            timeout=timeout_seconds,
            allow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
            },
        )
        if proxy_url:
            kwargs["proxy"] = proxy_url

        response = await session.get(url, **kwargs)
        resp_headers = {k.lower(): v for k, v in response.headers.items()}
        return response.text, response.status_code, resp_headers


# ---------------------------------------------------------------------------
# Strategy: httpx with HTTP/2
# ---------------------------------------------------------------------------

async def _fetch_with_httpx(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    timeout_seconds = timeout / 1000
    headers = random.choice(_HTTPX_HEADERS_LIST).copy()
    client_kwargs: dict[str, Any] = dict(
        follow_redirects=True, timeout=timeout_seconds, headers=headers, http2=True,
    )
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    async with httpx.AsyncClient(**client_kwargs) as client:
        response = await client.get(url)
        resp_headers = {k.lower(): v for k, v in response.headers.items()}
        return response.text, response.status_code, resp_headers


# ---------------------------------------------------------------------------
# Strategy: Browser with stealth + warm-up
# ---------------------------------------------------------------------------

async def _fetch_with_browser_stealth(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
    use_firefox: bool = False,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Browser fetch with stealth patches and warm-up navigation for hard sites."""
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    nav_timeout = max(request.timeout, 45000) if _is_hard_site(url) else request.timeout

    async with browser_pool.get_page(proxy=proxy, use_firefox=use_firefox) as page:
        referrer = random.choice(_GOOGLE_REFERRERS)

        # Warm-up: visit robots.txt first to establish cookies/session on hard sites
        if _is_hard_site(url):
            try:
                parsed = urlparse(url)
                warmup_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                await page.goto(warmup_url, wait_until="domcontentloaded", timeout=10000)
                await page.wait_for_timeout(random.randint(500, 1500))
            except Exception:
                pass

        # Main navigation
        response = await page.goto(
            url, wait_until="networkidle", timeout=nav_timeout, referer=referrer,
        )
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        await page.wait_for_timeout(random.randint(1000, 2500))

        # For hard sites: check if page is still a challenge and wait longer
        if _is_hard_site(url):
            html_check = await page.content()
            if _looks_blocked(html_check):
                logger.debug(f"Challenge detected for {url}, waiting for resolution...")
                await page.wait_for_timeout(random.randint(3000, 5000))
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(type="png", full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers


# ---------------------------------------------------------------------------
# Strategy: Aggressive browser — full human simulation + challenge busting
# ---------------------------------------------------------------------------

async def _fetch_with_browser_aggressive(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """
    Maximum anti-detection browser fetch:
    - Warm-up to root domain to establish session
    - Full human simulation (mouse, scroll, pauses)
    - Challenge page wait loop (checks every 2-4s for up to 15s)
    - Auto-click common overlays (cookie consent, etc.)
    """
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    async with browser_pool.get_page(proxy=proxy) as page:
        referrer = random.choice(_GOOGLE_REFERRERS)

        # Warm-up: visit root domain first
        try:
            parsed = urlparse(url)
            root_url = f"{parsed.scheme}://{parsed.netloc}/"
            if root_url != url:
                await page.goto(root_url, wait_until="domcontentloaded", timeout=15000, referer=referrer)
                await page.wait_for_timeout(random.randint(1000, 2000))
                vp = page.viewport_size or {"width": 1920, "height": 1080}
                await page.mouse.move(vp["width"] // 2, vp["height"] // 2, steps=10)
                await page.wait_for_timeout(random.randint(500, 1000))
        except Exception:
            pass

        # Navigate to target
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=60000, referer=referrer,
        )
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        # --- Full human simulation ---
        vp = page.viewport_size or {"width": 1920, "height": 1080}

        # Move to center
        await page.mouse.move(vp["width"] // 2, vp["height"] // 2, steps=random.randint(10, 20))
        await page.wait_for_timeout(random.randint(300, 600))

        # Random movements
        for _ in range(random.randint(4, 8)):
            x = random.randint(50, vp["width"] - 50)
            y = random.randint(50, vp["height"] - 50)
            await page.mouse.move(x, y, steps=random.randint(8, 25))
            await page.wait_for_timeout(random.randint(50, 300))

        # Smooth scroll down
        for _ in range(random.randint(3, 5)):
            await page.mouse.wheel(0, random.randint(80, 250))
            await page.wait_for_timeout(random.randint(150, 400))

        # Pause (reading)
        await page.wait_for_timeout(random.randint(1000, 2500))

        # Scroll back up
        for _ in range(random.randint(2, 4)):
            await page.mouse.wheel(0, random.randint(-200, -60))
            await page.wait_for_timeout(random.randint(150, 350))

        # --- Challenge wait loop: check every 2-4s up to ~15s ---
        for attempt in range(5):
            html_check = await page.content()
            if not _looks_blocked(html_check):
                break
            logger.debug(f"Still blocked attempt {attempt + 1} for {url}, waiting...")
            await page.wait_for_timeout(random.randint(2000, 4000))
            x = random.randint(100, vp["width"] - 100)
            y = random.randint(100, vp["height"] - 100)
            await page.mouse.move(x, y, steps=random.randint(5, 15))

        # Try clicking common overlay dismiss buttons
        for selector in [
            "button[id*='accept']", "button[id*='cookie']",
            "button[class*='accept']", "button[class*='cookie']",
            "[data-testid*='close']", "button:has-text('Accept')",
            "button:has-text('I agree')", "button:has-text('Got it')",
        ]:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=500):
                    await btn.click(timeout=1000)
                    await page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(type="png", full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers
