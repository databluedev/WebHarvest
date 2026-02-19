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


def _get_homepage(url: str) -> str | None:
    """For hard sites, return the homepage URL for warm-up navigation."""
    try:
        parsed = urlparse(url)
        if parsed.path.rstrip("/") == "" and not parsed.query:
            return None  # Already on homepage
        return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cookie consent acceptance
# ---------------------------------------------------------------------------

_COOKIE_ACCEPT_SELECTORS = [
    "#sp-cc-accept",                       # Amazon
    "[data-action-type='DISMISS']",        # Amazon
    "#onetrust-accept-btn-handler",        # OneTrust (common)
    "#cookie-consent-accept",
    "[aria-label*='Accept']",
    "button:has-text('Accept')",
    "button:has-text('Accept All')",
    "button:has-text('Got it')",
    "button:has-text('OK')",
]


async def _try_accept_cookies(page) -> None:
    """Best-effort click on cookie consent buttons. Fails silently."""
    for selector in _COOKIE_ACCEPT_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                await page.wait_for_timeout(random.randint(300, 600))
                return
        except Exception:
            continue


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

    # Amazon-style "no session" interstitial: very short body with specific combo
    if len(body_text) < 500:
        amazon_signals = sum(1 for p in [
            "continue shopping", "conditions of use", "privacy notice",
        ] if p in body_text)
        if amazon_signals >= 2:
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
    0. Check if URL is a document (PDF, DOCX) — handle separately
    1. curl_cffi with Chrome TLS impersonation (ALL sites including hard sites)
    2. httpx HTTP/2 fallback (non-hard sites only)
    3. Chromium browser with stealth + warm-up navigation
    4. Firefox browser if available (different engine/TLS)
    5. Chromium aggressive: human simulation + challenge wait loop
    """
    from app.core.cache import get_cached_scrape, set_cached_scrape
    from app.core.metrics import scrape_duration_seconds
    from app.services.document import detect_document_type, extract_pdf, extract_docx

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

    # Check if URL points to a document (PDF, DOCX) by extension
    doc_type = detect_document_type(url, content_type=None, raw_bytes=b"")
    if doc_type in ("pdf", "docx"):
        return await _handle_document_url(url, doc_type, request, proxy_manager, start_time)

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
                logger.info(f"curl_cffi blocked/failed for {url} (status={status_code}, best={len(raw_html_best)}), escalating")
        except Exception as e:
            logger.warning(f"curl_cffi exception for {url}: {e}")

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
            logger.warning(f"httpx exception for {url}: {e}")

    # === Strategy 2: Chromium browser with stealth ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_stealth(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Chromium stealth succeeded for {url} ({len(raw_html)} chars)")
            else:
                logger.warning(f"Chromium stealth blocked for {url} (html={len(raw_html or '')} chars)")
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Chromium stealth exception for {url}: {e}")

    # === Strategy 3: Firefox browser (only if no usable content yet) ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, use_firefox=True)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Firefox succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Firefox exception for {url}: {e}")

    # === Strategy 4: Aggressive browser — only if we truly have nothing good ===
    if not fetched:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_browser_aggressive(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Aggressive browser succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                logger.warning(f"Aggressive browser blocked for {url} (html={len(raw_html or '')})")
        except Exception as e:
            logger.warning(f"Aggressive browser exception for {url}: {e}")

    # --- Final fallback: use best available content even if blocked ---
    if not fetched:
        if raw_html_best:
            raw_html = raw_html_best
            logger.warning(f"All strategies blocked for {url}, using best available ({len(raw_html_best)} chars)")
        elif raw_html and _looks_blocked(raw_html):
            # Keep the blocked content — better than nothing
            logger.warning(f"All strategies blocked for {url}, using last result ({len(raw_html)} chars)")
        else:
            logger.error(f"All strategies failed for {url} — no content retrieved at all")
            duration = time.time() - start_time
            scrape_duration_seconds.observe(duration)
            return ScrapeData(
                metadata=PageMetadata(source_url=url, status_code=status_code or 0),
            )

    if not raw_html:
        logger.error(f"No raw_html for {url} despite fallback (best={len(raw_html_best)})")
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
# Document handling (PDF, DOCX)
# ---------------------------------------------------------------------------

async def _handle_document_url(
    url: str,
    doc_type: str,
    request: ScrapeRequest,
    proxy_manager,
    start_time: float,
) -> ScrapeData:
    """Fetch and extract content from document URLs (PDF, DOCX)."""
    from app.core.metrics import scrape_duration_seconds
    from app.services.document import extract_pdf, extract_docx, detect_document_type

    proxy_url = None
    if proxy_manager:
        proxy_obj = proxy_manager.get_random()
        if proxy_obj:
            proxy_url = proxy_manager.to_httpx(proxy_obj)

    # Fetch raw bytes
    raw_bytes = b""
    status_code = 0
    content_type = ""

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=request.timeout / 1000,
            **({"proxy": proxy_url} if proxy_url else {}),
        ) as client:
            resp = await client.get(url)
            raw_bytes = resp.content
            status_code = resp.status_code
            content_type = resp.headers.get("content-type", "")
    except Exception:
        pass

    # Fallback to curl_cffi
    if not raw_bytes:
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                kwargs: dict[str, Any] = {"timeout": request.timeout / 1000, "allow_redirects": True}
                if proxy_url:
                    kwargs["proxy"] = proxy_url
                resp = await session.get(url, **kwargs)
                raw_bytes = resp.content
                status_code = resp.status_code
                content_type = dict(resp.headers).get("content-type", "")
        except Exception:
            pass

    if not raw_bytes:
        duration = time.time() - start_time
        scrape_duration_seconds.observe(duration)
        return ScrapeData(
            metadata=PageMetadata(source_url=url, status_code=status_code or 0),
        )

    # Re-detect type from content-type header and bytes
    actual_type = detect_document_type(url, content_type, raw_bytes)

    if actual_type == "pdf":
        doc_result = await extract_pdf(raw_bytes)
    elif actual_type == "docx":
        doc_result = await extract_docx(raw_bytes)
    else:
        # Not actually a document, return the text as HTML
        duration = time.time() - start_time
        scrape_duration_seconds.observe(duration)
        return ScrapeData(
            markdown=raw_bytes.decode("utf-8", errors="replace"),
            metadata=PageMetadata(source_url=url, status_code=status_code),
        )

    # Build ScrapeData from DocumentResult
    doc_metadata = doc_result.metadata.copy()
    doc_metadata["source_url"] = url
    doc_metadata["status_code"] = status_code

    metadata = PageMetadata(
        title=doc_metadata.get("title", ""),
        source_url=url,
        status_code=status_code,
        word_count=doc_result.word_count,
    )

    duration = time.time() - start_time
    scrape_duration_seconds.observe(duration)

    return ScrapeData(
        markdown=doc_result.markdown if "markdown" in request.formats else None,
        html=None,
        metadata=metadata,
        structured_data={"document_metadata": doc_result.metadata} if "structured_data" in request.formats else None,
    )


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
    """Fast browser fetch: domcontentloaded + short networkidle."""
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    async with browser_pool.get_page(proxy=proxy, use_firefox=use_firefox, target_url=url) as page:
        referrer = random.choice(_GOOGLE_REFERRERS)

        # Warm-up navigation for hard sites: visit homepage first to build session
        if _is_hard_site(url):
            homepage = _get_homepage(url)
            if homepage:
                try:
                    await page.goto(homepage, wait_until="domcontentloaded", timeout=10000, referer=referrer)
                    await page.wait_for_timeout(random.randint(1500, 3000))
                    await _try_accept_cookies(page)
                    await page.wait_for_timeout(random.randint(500, 1000))
                except Exception:
                    pass  # Best-effort warm-up

        # Fast navigation: domcontentloaded first (doesn't hang on analytics)
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=15000, referer=referrer,
        )
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        # Short networkidle — give JS 5s to render, don't block forever
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        await page.wait_for_timeout(random.randint(500, 1000))

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
    Last-resort browser fetch with human simulation.
    Kept fast: ~10-15s max. Only used when stealth fails.
    """
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    async with browser_pool.get_page(proxy=proxy, target_url=url) as page:
        referrer = random.choice(_GOOGLE_REFERRERS)

        # Warm-up navigation for hard sites
        if _is_hard_site(url):
            homepage = _get_homepage(url)
            if homepage:
                try:
                    await page.goto(homepage, wait_until="domcontentloaded", timeout=10000, referer=referrer)
                    await page.wait_for_timeout(random.randint(1500, 3000))
                    await _try_accept_cookies(page)
                    await page.wait_for_timeout(random.randint(500, 1000))
                except Exception:
                    pass

        # Navigate to target
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=15000, referer=referrer,
        )
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Human simulation — realistic browsing behavior
        vp = page.viewport_size or {"width": 1920, "height": 1080}

        # Move to a natural starting point (top area, like reading page header)
        await page.mouse.move(
            vp["width"] // 2 + random.randint(-100, 100),
            random.randint(80, 200),
            steps=random.randint(15, 25),
        )
        await page.wait_for_timeout(random.randint(300, 700))

        # 4-6 random mouse movements across the page
        for _ in range(random.randint(4, 6)):
            x = random.randint(100, vp["width"] - 100)
            y = random.randint(100, vp["height"] - 100)
            await page.mouse.move(x, y, steps=random.randint(10, 20))
            await page.wait_for_timeout(random.randint(200, 600))

        # Try cookie acceptance
        await _try_accept_cookies(page)

        # Multiple scrolls down
        for _ in range(random.randint(2, 3)):
            await page.mouse.wheel(0, random.randint(200, 500))
            await page.wait_for_timeout(random.randint(400, 800))

        # Scroll back up (humans don't only scroll down)
        await page.mouse.wheel(0, -random.randint(100, 200))
        await page.wait_for_timeout(random.randint(300, 600))

        # More mouse movement after scrolling
        for _ in range(random.randint(2, 3)):
            x = random.randint(100, vp["width"] - 100)
            y = random.randint(100, vp["height"] - 100)
            await page.mouse.move(x, y, steps=random.randint(8, 15))
            await page.wait_for_timeout(random.randint(200, 500))

        # Challenge check with re-check
        html_check = await page.content()
        if _looks_blocked(html_check):
            await page.wait_for_timeout(random.randint(3000, 5000))
            html_check2 = await page.content()
            if _looks_blocked(html_check2):
                await page.wait_for_timeout(random.randint(3000, 5000))

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
