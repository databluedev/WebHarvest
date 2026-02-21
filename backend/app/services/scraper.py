import asyncio
import base64
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from app.schemas.scrape import ScrapeRequest, ScrapeData, PageMetadata
from app.services.browser import browser_pool
from app.services.content import (
    extract_main_content,
    extract_and_convert,
    apply_tag_filters,
    html_to_markdown,
    extract_links,
    extract_links_detailed,
    extract_metadata,
    extract_structured_data,
    extract_headings,
    extract_images,
)
from app.services.strategy_cache import (
    get_domain_strategy,
    record_strategy_result,
    get_starting_tier,
)

from app.config import settings
from app.core.redis import redis_client as _redis

logger = logging.getLogger(__name__)


async def domain_throttle(domain: str, delay: float = 0.5) -> None:
    """Redis-backed per-domain rate limiter. Ensures at least `delay` seconds between requests to the same domain."""
    key = f"throttle:{domain}"
    last = await _redis.get(key)
    if last is not None:
        wait = float(last) + delay - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
    await _redis.set(key, str(time.time()), ex=int(delay * 2) + 1)


# Thread pool for CPU-bound content extraction
_extraction_executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# HTTP session pools — reuse connections across requests (saves TLS handshake)
# ---------------------------------------------------------------------------
_httpx_client: httpx.AsyncClient | None = None
_httpx_loop_id: int | None = None  # Track which event loop the client belongs to
_curl_sessions: dict[str, Any] = {}  # profile -> AsyncSession
_curl_loop_id: int | None = None  # Track which event loop curl sessions belong to


async def cleanup_async_pools() -> None:
    """Close all pooled async clients/sessions.

    MUST be called before the event loop closes (e.g. in Celery _run_async)
    so that no stale sessions survive referencing a dead loop.
    """
    global _httpx_client, _httpx_loop_id, _curl_loop_id
    global _stealth_client, _stealth_loop_id

    # httpx client
    if _httpx_client is not None:
        try:
            await _httpx_client.aclose()
        except Exception:
            pass
        _httpx_client = None
        _httpx_loop_id = None

    # curl_cffi sessions (AsyncSession.close() is a coroutine)
    for session in _curl_sessions.values():
        try:
            await session.close()
        except Exception:
            pass
    _curl_sessions.clear()
    _curl_loop_id = None

    # stealth engine client
    if _stealth_client is not None:
        try:
            await _stealth_client.aclose()
        except Exception:
            pass
        _stealth_client = None
        _stealth_loop_id = None


async def _get_httpx_client(proxy_url: str | None = None) -> httpx.AsyncClient:
    """Get or create a reusable httpx client (no proxy variant).

    Recreates the client when running in a different event loop (Celery workers
    create a fresh loop per task).
    """
    global _httpx_client, _httpx_loop_id
    if proxy_url:
        # Proxied requests need fresh clients (different proxy per request)
        return httpx.AsyncClient(
            follow_redirects=True, http2=True, timeout=30, proxy=proxy_url
        )
    current_loop_id = id(asyncio.get_running_loop())
    if (
        _httpx_client is None
        or _httpx_client.is_closed
        or _httpx_loop_id != current_loop_id
    ):
        _httpx_client = httpx.AsyncClient(follow_redirects=True, http2=True, timeout=30)
        _httpx_loop_id = current_loop_id
    return _httpx_client


def _get_curl_session(profile: str = "chrome124"):
    """Get or create a reusable curl_cffi session for a given TLS profile.

    Recreates sessions when running in a different event loop (Celery workers
    create a fresh loop per task).  Old sessions are explicitly closed before
    clearing to prevent "Event loop is closed" errors.
    """
    global _curl_loop_id
    from curl_cffi.requests import AsyncSession as CurlAsyncSession

    current_loop_id = id(asyncio.get_running_loop())
    if _curl_loop_id != current_loop_id:
        # Stale sessions are bound to a dead event loop — AsyncSession.close()
        # is a coroutine, but we can't await it here (sync context) and the old
        # loop is gone anyway.  Just drop the references; cleanup_async_pools()
        # handles proper async teardown before loop.close().
        _curl_sessions.clear()
        _curl_loop_id = current_loop_id
    if profile not in _curl_sessions:
        _curl_sessions[profile] = CurlAsyncSession(impersonate=profile)
    return _curl_sessions[profile]


# ---------------------------------------------------------------------------
# Stealth Engine sidecar client (Patchright + Camoufox microservice)
# ---------------------------------------------------------------------------
_stealth_client: httpx.AsyncClient | None = None
_stealth_loop_id: int | None = None


async def _get_stealth_client() -> httpx.AsyncClient:
    """Get or create a reusable httpx client for the stealth-engine sidecar."""
    global _stealth_client, _stealth_loop_id
    current_loop_id = id(asyncio.get_running_loop())
    if (
        _stealth_client is None
        or _stealth_client.is_closed
        or _stealth_loop_id != current_loop_id
    ):
        _stealth_client = httpx.AsyncClient(timeout=60)
        _stealth_loop_id = current_loop_id
    return _stealth_client


async def _fetch_via_stealth_engine(
    url: str,
    request: "ScrapeRequest",
    use_firefox: bool = False,
    proxy: dict | None = None,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Fetch a URL via the stealth-engine microservice.

    Returns the same 5-tuple as _fetch_with_browser_stealth:
    (html, status_code, screenshot_b64, action_screenshots, response_headers)

    Raises on any failure so _race_strategies handles fallback.
    """
    stealth_url = settings.STEALTH_ENGINE_URL
    if not stealth_url:
        raise RuntimeError("STEALTH_ENGINE_URL not configured")

    payload: dict = {
        "url": url,
        "timeout": request.timeout,
        "wait_after_load": getattr(request, "wait_for", 0) or getattr(request, "wait_after_load", 0),
        "use_firefox": use_firefox,
        "screenshot": "screenshot" in getattr(request, "formats", []),
        "mobile": getattr(request, "mobile", False),
    }

    if getattr(request, "headers", None):
        payload["headers"] = request.headers
    if getattr(request, "cookies", None):
        payload["cookies"] = request.cookies
    if getattr(request, "actions", None):
        payload["actions"] = request.actions
    if proxy:
        payload["proxy"] = proxy

    client = await _get_stealth_client()
    resp = await client.post(f"{stealth_url}/scrape", json=payload)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"stealth-engine error: {data.get('error', 'unknown')}")

    return (
        data.get("html", ""),
        data.get("status_code", 0),
        data.get("screenshot"),
        data.get("action_screenshots", []),
        data.get("response_headers", {}),
    )


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
    "please click here if you are not redirected",
    "if you are not redirected within",
    "having trouble accessing google",
    # Akamai Bot Manager
    "your connection needs to be verified",
    "connection is being verified",
    "please verify your identity",
]

# Exact domain matches
_HARD_SITES_EXACT = {
    "google.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "zillow.com",
    "indeed.com",
    "glassdoor.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "cloudflare.com",
    "netflix.com",
    "spotify.com",
    "ticketmaster.com",
    "stubhub.com",
    "craigslist.org",
    "yelp.com",
}

# Brand patterns — match any TLD variant (nike.com, nike.in, nike.co.uk, etc.)
_HARD_SITE_BRANDS = {
    "amazon",
    "nike",
    "adidas",
    "ebay",
    "booking",
    "airbnb",
    "expedia",
    "flipkart",
    "myntra",
    "ajio",
    "zara",
    "hm",
}

# ---------------------------------------------------------------------------
# Header rotation pool — 10 realistic browser header sets
# ---------------------------------------------------------------------------

_HEADER_ROTATION_POOL = [
    # 0: Chrome 123 on Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="123", "Google Chrome";v="123", "Not:A-Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    },
    # 1: Chrome 124 on macOS
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
    # 2: Chrome 125 on Linux
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    # 3: Firefox 125 on Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    },
    # 4: Firefox 126 on macOS
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    # 5: Safari 17.4 on macOS
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    },
    # 6: Edge 124 on Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    # 7: Chrome with en-IN locale (for Indian sites)
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    # 8: Chrome with Google cross-site referrer
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
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
    },
    # 9: Chrome 124 on Windows (en-GB variant)
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
]

# ---------------------------------------------------------------------------
# curl_cffi TLS fingerprint profiles
# ---------------------------------------------------------------------------

_CURL_CFFI_PROFILES = ["chrome124", "chrome120", "safari17_0", "safari15_5", "edge101"]

_LOCALE_MAP = {
    ".in": "en-IN,en;q=0.9,hi;q=0.8",
    ".co.uk": "en-GB,en;q=0.9",
    ".de": "de-DE,de;q=0.9,en;q=0.8",
    ".fr": "fr-FR,fr;q=0.9,en;q=0.8",
    ".co.jp": "ja-JP,ja;q=0.9,en;q=0.8",
    ".es": "es-ES,es;q=0.9,en;q=0.8",
    ".it": "it-IT,it;q=0.9,en;q=0.8",
    ".com.au": "en-AU,en;q=0.9",
    ".ca": "en-CA,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Bot detection script patterns (for request interception)
# ---------------------------------------------------------------------------

_BOT_DETECTION_PATTERNS = [
    # Third-party bot detection services only.
    # DO NOT block first-party scripts (e.g. Amazon's fls/unagi) — blocking them
    # signals bot activity because the server expects them to execute and report back.
    r"px-captcha",
    r".*\.perimeterx\.",
    r"js\.datadome\.co",
    r"api\.datadome\.co",
    r"challenges\.cloudflare\.com",
    r"cdn-cgi/challenge-platform",
    r".*\.kasada\.io",
    r".*\.shape\.ag",
    r"recaptcha",
]

_BOT_DETECTION_REGEX: re.Pattern | None = None  # Reset on pattern change

_GOOGLE_REFERRERS = [
    "https://www.google.com/",
    "https://www.google.com/search?q=",
    "https://www.google.co.uk/",
]


# ---------------------------------------------------------------------------
# Documentation framework detection — wait for content, not just networkidle
# ---------------------------------------------------------------------------

# Map of doc framework → CSS selectors that indicate content has loaded
_DOC_FRAMEWORK_CONTENT_SELECTORS: dict[str, list[str]] = {
    "gitbook": [".gitbook-root main", ".book-body .page-inner", ".page-wrapper .page-inner"],
    "honkit": [".book-body .page-inner", ".book-body .markdown-section", ".book .body-inner"],
    "docusaurus": [".theme-doc-markdown", "#__docusaurus main article", ".docMainContainer article"],
    "mkdocs": [".md-content article", ".md-content", "[data-md-component='content'] article"],
    "readthedocs": [".rst-content", ".wy-nav-content .section", ".document .section"],
    "sphinx": [".body", ".sphinxsidebar + .document", ".documentwrapper .body"],
    "vuepress": [".theme-default-content", ".page .content__default", ".page .theme-container main"],
    "vitepress": [".VPDoc .vp-doc", ".VPContent main", ".vp-doc"],
    "nextra": ["article.nextra-content", "main article", ".nextra-body main"],
    "hugo": [".book-page article", "main article", ".prose"],
    "mdbook": ["#content main", "#content .content", "main"],
    "starlight": ["main [data-has-sidebar] article", "main article", "[data-pagefind-body]"],
    "mintlify": ["main article", "article.prose"],
}

# Detect selectors: framework name → list of selectors to check in the HTML
_DOC_FRAMEWORK_DETECT_SELECTORS: dict[str, list[str]] = {
    "gitbook": ['[class*="gitbook"]', ".gitbook-root", ".book-summary"],
    "honkit": [".book.with-summary", ".book-summary", ".book-header"],
    "docusaurus": ["#__docusaurus", '[class*="docusaurus"]'],
    "mkdocs": [".md-sidebar", ".md-content", '[data-md-component="sidebar"]'],
    "readthedocs": [".wy-nav-side", ".rst-content"],
    "sphinx": [".sphinxsidebar", ".sphinxsidebarwrapper"],
    "vuepress": [".theme-default-content", ".theme-container"],
    "vitepress": [".VPSidebar", ".VPDoc", "#VPContent"],
    "nextra": ['[class*="nextra"]', ".nextra-sidebar-container"],
    "hugo": [".book-menu", ".book-page"],
    "mdbook": [".sidebar-scrollbox", "#sidebar"],
    "starlight": ["[data-has-sidebar]"],
    "mintlify": ['[class*="mintlify"]'],
}


async def _wait_for_doc_content(page, timeout_ms: int = 5000) -> str | None:
    """Detect doc framework and wait for its content selector to appear.

    Returns the detected framework name, or None if not a doc site.
    This replaces blind networkidle waiting with targeted content readiness detection.
    """
    # Quick detection: check which framework selectors exist
    detected = None
    for fw_name, selectors in _DOC_FRAMEWORK_DETECT_SELECTORS.items():
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    detected = fw_name
                    break
            except Exception:
                pass
        if detected:
            break

    if not detected:
        return None

    # Wait for the framework's content selectors to appear
    content_selectors = _DOC_FRAMEWORK_CONTENT_SELECTORS.get(detected, [])
    for sel in content_selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout_ms)
            logger.debug(f"Doc framework '{detected}' content ready via '{sel}'")
            return detected
        except Exception:
            continue

    logger.debug(f"Doc framework '{detected}' detected but content selectors timed out")
    return detected


def _is_hard_site(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        # Exact match or subdomain match
        if any(domain == d or domain.endswith("." + d) for d in _HARD_SITES_EXACT):
            return True
        # Brand pattern match: extract brand name (first part before TLD)
        # e.g. "nike.in" → "nike", "amazon.co.uk" → "amazon"
        brand = domain.split(".")[0]
        return brand in _HARD_SITE_BRANDS
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
# Locale / header helpers
# ---------------------------------------------------------------------------


def _get_locale_for_url(url: str) -> str:
    """Return locale-aware Accept-Language based on domain TLD."""
    try:
        domain = urlparse(url).netloc.lower()
        # Check longest suffixes first to match .com.au before .au
        for suffix, locale in sorted(_LOCALE_MAP.items(), key=lambda x: -len(x[0])):
            if domain.endswith(suffix):
                return locale
    except Exception:
        pass
    return "en-US,en;q=0.9"


def _get_headers_for_profile(profile: str, url: str) -> dict[str, str]:
    """Return appropriate HTTP headers for a curl_cffi TLS profile."""
    locale = _get_locale_for_url(url)
    base: dict[str, str] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": locale,
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    if profile.startswith("safari"):
        # Safari doesn't send Sec-Ch-Ua headers
        base.pop("Sec-Fetch-User", None)
        base["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
    elif profile.startswith("edge"):
        base["Sec-Ch-Ua"] = (
            '"Chromium";v="101", "Microsoft Edge";v="101", "Not A;Brand";v="99"'
        )
        base["Sec-Ch-Ua-Mobile"] = "?0"
        base["Sec-Ch-Ua-Platform"] = '"Windows"'
    elif profile.startswith("chrome"):
        version = profile.replace("chrome", "")
        base["Sec-Ch-Ua"] = (
            f'"Chromium";v="{version}", "Google Chrome";v="{version}", "Not-A.Brand";v="99"'
        )
        base["Sec-Ch-Ua-Mobile"] = "?0"
        base["Sec-Ch-Ua-Platform"] = '"Windows"'

    return base


# ---------------------------------------------------------------------------
# Bot detection request interception
# ---------------------------------------------------------------------------


def _get_bot_detection_regex() -> re.Pattern:
    """Compile and cache the bot detection URL regex."""
    global _BOT_DETECTION_REGEX
    if _BOT_DETECTION_REGEX is None:
        combined = "|".join(f"({p})" for p in _BOT_DETECTION_PATTERNS)
        _BOT_DETECTION_REGEX = re.compile(combined, re.IGNORECASE)
    return _BOT_DETECTION_REGEX


async def _setup_request_interception(page, url: str) -> None:
    """Block bot detection scripts via request interception. Only active for hard sites."""
    if not _is_hard_site(url):
        return

    regex = _get_bot_detection_regex()

    async def _handle_route(route):
        req_url = route.request.url
        if regex.search(req_url):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", _handle_route)


# ---------------------------------------------------------------------------
# Cookie consent acceptance
# ---------------------------------------------------------------------------

_COOKIE_ACCEPT_SELECTORS = [
    "#sp-cc-accept",  # Amazon
    "[data-action-type='DISMISS']",  # Amazon
    "#onetrust-accept-btn-handler",  # OneTrust (common)
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
                await page.wait_for_timeout(random.randint(100, 300))
                return
        except Exception:
            continue


_GOOGLE_CONSENT_SELECTORS = [
    "button:has-text('Accept all')",
    "button:has-text('Accept')",
    "#L2AGLb",
    "button:has-text('I agree')",
]


async def _try_accept_google_consent(page) -> None:
    """Best-effort click on Google GDPR/consent buttons."""
    for selector in _GOOGLE_CONSENT_SELECTORS:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(random.randint(200, 400))
                return
        except Exception:
            continue


def _looks_blocked(html: str) -> bool:
    if not html:
        return True

    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body_html = body_match.group(1) if body_match else html

    # Strip <script> and <style> tags AND their content before measuring text
    visible_html = re.sub(
        r"<script[^>]*>.*?</script>", " ", body_html, flags=re.DOTALL | re.IGNORECASE
    )
    visible_html = re.sub(
        r"<style[^>]*>.*?</style>", " ", visible_html, flags=re.DOTALL | re.IGNORECASE
    )
    visible_html = re.sub(
        r"<noscript[^>]*>.*?</noscript>",
        " ",
        visible_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body_text = re.sub(r"<[^>]+>", " ", visible_html).strip().lower()
    # Collapse whitespace for accurate length measurement
    body_text = re.sub(r"\s+", " ", body_text)

    # Pages with substantial visible text content are never block pages
    if len(body_text) > 3000:
        return False

    # Only check block patterns on very short pages — pages with moderate
    # text (e.g. partially loaded product pages) shouldn't be flagged just
    # because they contain words like "captcha" in a footer link or script ref.
    if len(body_text) < 800:
        for pattern in _BLOCK_PATTERNS:
            if pattern in body_text:
                logger.warning(f"_looks_blocked: matched '{pattern}' (body_text={len(body_text)} chars)")
                return True

    # Only check head for patterns that STRONGLY indicate a block page
    # Avoid generic words like "captcha" / "robot" which appear in normal content
    head = html[:5000].lower()
    for pattern in [
        "javascript is disabled",
        "enable javascript",
        "attention required",
        "just a moment",
        "checking your browser",
        "please wait while we verify",
        "verify you are human",
        "are you a robot",
        "not a robot",
        "please click here if you are not redirected",
        "having trouble accessing google",
    ]:
        if pattern in head:
            logger.warning(f"_looks_blocked: head matched '{pattern}' (body_text={len(body_text)} chars)")
            return True

    if len(body_text) < 300 and ("<noscript" in html.lower()):
        logger.warning(f"_looks_blocked: noscript + short body ({len(body_text)} chars)")
        return True

    # Google redirect/interstitial page (from Google Cache attempts)
    if len(body_text) < 500:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
        )
        if title_match and "google" in title_match.group(1).lower():
            return True

    # Amazon-style "no session" interstitial: very short body with specific combo
    if len(body_text) < 500:
        amazon_signals = sum(
            1
            for p in [
                "continue shopping",
                "conditions of use",
                "privacy notice",
            ]
            if p in body_text
        )
        if amazon_signals >= 2:
            return True

    return False


# ---------------------------------------------------------------------------
# Cache/archive content strippers
# ---------------------------------------------------------------------------


def _strip_google_cache_banner(html: str) -> str:
    """Remove Google's cache header/banner from cached HTML."""
    html = re.sub(
        r'<div[^>]*(?:id|class)=["\']google-cache-hdr["\'][^>]*>.*?</div>\s*(?:</div>)*',
        "",
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r'<div[^>]*style=["\'][^"\']*text-align:\s*center[^"\']*["\'][^>]*>.*?This is Google\'s cache.*?</div>',
        "",
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html


def _strip_wayback_toolbar(html: str) -> str:
    """Remove Wayback Machine injected toolbar and scripts."""
    html = re.sub(
        r"<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->",
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"<script[^>]*(?:wombat|archive\.org)[^>]*>.*?</script>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<(?:link|style)[^>]*(?:archive\.org|wayback)[^>]*(?:/>|>.*?</(?:link|style)>)",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html


# ---------------------------------------------------------------------------
# Race helper — runs multiple strategy coroutines, returns first success
# ---------------------------------------------------------------------------


class RaceResult:
    """Result from _race_strategies including winner and best fallback."""

    __slots__ = ("winner_name", "winner_result", "best_html", "best_result")

    def __init__(self):
        self.winner_name: str | None = None
        self.winner_result = None
        self.best_html: str = ""
        self.best_result = None

    @property
    def success(self) -> bool:
        return self.winner_name is not None


async def _race_strategies(
    coros: list[tuple[str, Any]],
    url: str,
    validate_fn=None,
    timeout: float | None = None,
) -> RaceResult:
    """Run multiple strategy coroutines concurrently, return first success.

    Args:
        coros: List of (strategy_name, coroutine) tuples
        url: URL being scraped (for logging)
        validate_fn: Optional function to validate result.
        timeout: Max seconds for this race. None = no timeout.

    Returns:
        RaceResult with winner (if any) and best fallback HTML.
    """
    race = RaceResult()
    if not coros:
        return race

    if validate_fn is None:

        def validate_fn(result):
            html = result[0] if isinstance(result, tuple) else result
            if not html:
                return False
            if isinstance(result, tuple) and len(result) == 3:
                return result[1] < 400 and not _looks_blocked(html)
            if isinstance(result, tuple) and len(result) == 5:
                return not _looks_blocked(html)
            return not _looks_blocked(html)

    async def _named_wrapper(name: str, coro):
        try:
            result = await coro
            return name, result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Race: {name} failed for {url}: {e}")
            raise

    # Suppress expected Playwright TargetClosedError during race cancellation
    loop = asyncio.get_running_loop()
    _original_handler = loop.get_exception_handler()

    def _suppress_playwright_errors(loop_ref, context):
        exc = context.get("exception")
        if exc:
            exc_name = type(exc).__name__
            if "TargetClosedError" in exc_name or "Target" in exc_name:
                return
        if _original_handler:
            _original_handler(loop_ref, context)
        else:
            loop_ref.default_exception_handler(context)

    loop.set_exception_handler(_suppress_playwright_errors)

    tasks = [
        asyncio.create_task(_named_wrapper(name, coro), name=name)
        for name, coro in coros
    ]

    pending = set(tasks)
    race_start = time.time()

    try:
        while pending:
            # Calculate remaining timeout
            wait_timeout = None
            if timeout is not None:
                elapsed = time.time() - race_start
                wait_timeout = max(0.1, timeout - elapsed)
                if elapsed >= timeout:
                    logger.warning(f"Race timeout ({timeout}s) for {url}, pending: {[t.get_name() for t in pending]}")
                    break

            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=wait_timeout,
            )

            if not done:
                # Timeout on wait — no task completed in time
                logger.warning(f"Race: wait timeout for {url}, pending: {[t.get_name() for t in pending]}")
                break

            for task in done:
                try:
                    name, result = task.result()

                    # Track best HTML for fallback regardless of validation
                    html = result[0] if isinstance(result, tuple) else ""
                    if html and len(html) > len(race.best_html):
                        race.best_html = html
                        race.best_result = result

                    if validate_fn(result):
                        race.winner_name = name
                        race.winner_result = result
                        logger.info(f"Race winner: {name} for {url}")
                        for p in pending:
                            p.cancel()
                        pending = set()
                        break
                    else:
                        html_len = len(result[0]) if isinstance(result, tuple) and result[0] else 0
                        logger.warning(f"Race: {name} failed validation for {url} (html={html_len} chars)")
                except (asyncio.CancelledError, Exception) as e:
                    if not isinstance(e, asyncio.CancelledError):
                        logger.warning(f"Race: strategy exception for {url}: {e}")
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        loop.set_exception_handler(_original_handler)

    return race


# ---------------------------------------------------------------------------
# Main scrape
# ---------------------------------------------------------------------------


async def scrape_url(
    request: ScrapeRequest,
    proxy_manager=None,
    crawl_session=None,
) -> ScrapeData:
    """
    Scrape a URL with parallel tier architecture for maximum speed.

    Tier 0: Strategy cache hit → try last known working strategy
    Tier 1: HTTP parallel → race(curl_cffi_multi, httpx)
    Tier 2: Browser race → race(chromium_stealth, firefox_stealth)
    Tier 3: Heavy race (hard sites) → race(google_search, advanced_prewarm)
    Tier 4: Fallback parallel → race(google_cache, wayback)
    """
    from app.core.cache import get_cached_scrape, set_cached_scrape
    from app.core.metrics import scrape_duration_seconds
    from app.services.document import detect_document_type

    url = request.url
    start_time = time.time()

    # Domain throttle — ensure polite delay between requests to same domain
    domain = urlparse(url).netloc
    if domain:
        await domain_throttle(domain)

    # Circuit breaker — reject requests to domains with repeated failures
    # Skip for hard sites: they have dedicated anti-detection strategies and
    # are expected to sometimes block; the breaker would prematurely cut them off.
    if domain and not _is_hard_site(url):
        from app.services.circuit_breaker import check_breaker, CircuitBreakerOpenError

        try:
            await check_breaker(domain)
        except CircuitBreakerOpenError:
            raise

    use_cache = (
        not request.actions
        and "screenshot" not in request.formats
        and not request.extract
    )
    if use_cache:
        cached = await get_cached_scrape(url, request.formats)
        if cached:
            try:
                return ScrapeData(**cached)
            except Exception:
                pass

    # Check if URL points to a document by extension
    doc_type = detect_document_type(url, content_type=None, raw_bytes=b"")
    if doc_type in ("pdf", "docx", "xlsx", "pptx", "csv", "rtf", "epub"):
        return await _handle_document_url(
            url, doc_type, request, proxy_manager, start_time
        )

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
        request.actions or "screenshot" in request.formats or request.wait_for > 0
    )

    fetched = False
    winning_strategy = None
    winning_tier = None

    # --- Strategy cache lookup ---
    strategy_data = await get_domain_strategy(url)
    starting_tier = get_starting_tier(strategy_data, hard_site)

    # Helper to unpack race results and update state
    def _unpack_http_result(result):
        """Unpack (html, status, headers) tuple."""
        return result[0], result[1], result[2]

    def _unpack_browser_result(result):
        """Unpack (html, status, screenshot, action_screenshots, headers) tuple."""
        return result[0], result[1], result[2], result[3], result[4]

    # === Tier 0: Strategy cache hit — try last known working strategy ===
    _is_browser_strategy = False
    if starting_tier == 0 and strategy_data:
        last_strategy = strategy_data.get("last_success_strategy", "")
        _is_browser_strategy = last_strategy in (
            "chromium_stealth",
            "firefox_stealth",
            "google_search_chain",
            "advanced_prewarm",
            "stealth_chromium",
            "stealth_firefox",
        )

    if (
        starting_tier == 0
        and strategy_data
        and (not needs_browser or _is_browser_strategy)
    ):
        last_strategy = strategy_data.get("last_success_strategy", "")
        strategy_data.get("last_success_tier", 1)
        tier_start = time.time()

        _custom_headers = getattr(request, "headers", None)
        _custom_cookies = getattr(request, "cookies", None)
        try:
            if last_strategy.startswith("curl_cffi:") and not needs_browser:
                profile = last_strategy.split(":", 1)[1]
                result = await _fetch_with_curl_cffi_single(
                    url,
                    request.timeout,
                    profile=profile,
                    proxy_url=proxy_url,
                    custom_headers=_custom_headers,
                    custom_cookies=_custom_cookies,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")
            elif last_strategy == "httpx" and not needs_browser:
                result = await _fetch_with_httpx(
                    url,
                    request.timeout,
                    proxy_url=proxy_url,
                    custom_headers=_custom_headers,
                    custom_cookies=_custom_cookies,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")
            elif last_strategy in ("chromium_stealth", "firefox_stealth"):
                use_ff = last_strategy == "firefox_stealth"
                result = await _fetch_with_browser_stealth(
                    url, request, proxy=proxy_playwright, use_firefox=use_ff
                )
                html = result[0]
                if html and not _looks_blocked(html):
                    (
                        raw_html,
                        status_code,
                        screenshot_b64,
                        action_screenshots,
                        response_headers,
                    ) = result
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")
            elif last_strategy == "google_search_chain":
                result = await _fetch_with_google_search_chain(
                    url, request, proxy=proxy_playwright
                )
                html = result[0]
                if html and not _looks_blocked(html):
                    (
                        raw_html,
                        status_code,
                        screenshot_b64,
                        action_screenshots,
                        response_headers,
                    ) = result
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")
            elif last_strategy == "advanced_prewarm":
                result = await _fetch_with_advanced_prewarm(
                    url, request, proxy=proxy_playwright
                )
                html = result[0]
                if html and not _looks_blocked(html):
                    (
                        raw_html,
                        status_code,
                        screenshot_b64,
                        action_screenshots,
                        response_headers,
                    ) = result
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")
            elif last_strategy in ("stealth_chromium", "stealth_firefox"):
                use_ff = last_strategy == "stealth_firefox"
                result = await _fetch_via_stealth_engine(
                    url, request, use_firefox=use_ff, proxy=proxy_playwright
                )
                html = result[0]
                if html and not _looks_blocked(html):
                    (
                        raw_html,
                        status_code,
                        screenshot_b64,
                        action_screenshots,
                        response_headers,
                    ) = result
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
                    logger.info(f"Strategy cache hit for {url}: {last_strategy}")

            if fetched:
                elapsed_ms = (time.time() - tier_start) * 1000
                await record_strategy_result(url, winning_strategy, 0, True, elapsed_ms)
        except Exception as e:
            logger.debug(f"Strategy cache hit attempt failed for {url}: {e}")

    # === Tier 0.5: Cookie HTTP — curl_cffi with browser cookies (crawl mode) ===
    if not fetched and crawl_session and not needs_browser:
        tier_start = time.time()
        try:
            cookies = await crawl_session.get_cookies_for_http()
            if cookies:
                result = await _fetch_with_cookie_http(
                    url, request.timeout, cookies, proxy_url=proxy_url
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = "cookie_http"
                    winning_tier = 0
                    elapsed_ms = (time.time() - tier_start) * 1000
                    await record_strategy_result(
                        url, "cookie_http", 0, True, elapsed_ms
                    )
                    logger.info(f"Cookie HTTP hit for {url}")
        except Exception as e:
            logger.debug(f"Cookie HTTP failed for {url}: {e}")

    # Helper to accumulate best HTML + screenshot from race losers
    screenshot_b64_best = None
    action_screenshots_best = []

    def _update_best(race: RaceResult):
        nonlocal raw_html_best, screenshot_b64_best, action_screenshots_best
        if race.best_html and len(race.best_html) > len(raw_html_best):
            raw_html_best = race.best_html
        # Preserve screenshot from browser race results (5-tuple)
        if (
            race.best_result
            and isinstance(race.best_result, tuple)
            and len(race.best_result) == 5
        ):
            _, _, best_ss, best_action_ss, _ = race.best_result
            if best_ss and not screenshot_b64_best:
                screenshot_b64_best = best_ss
                action_screenshots_best = best_action_ss or []

    def _validate_browser(result):
        html = result[0] if isinstance(result, tuple) else result
        return bool(html) and not _looks_blocked(html)

    # === Tier 1: HTTP parallel — race(curl_cffi_multi, httpx) ===
    custom_headers = getattr(request, "headers", None)
    custom_cookies = getattr(request, "cookies", None)
    if not fetched and not needs_browser and starting_tier <= 1:
        tier_start = time.time()

        http_coros = [
            (
                "curl_cffi_multi",
                _fetch_with_curl_cffi_multi(
                    url,
                    request.timeout,
                    proxy_url=proxy_url,
                    custom_headers=custom_headers,
                    custom_cookies=custom_cookies,
                ),
            ),
        ]
        if not hard_site:
            http_coros.append(
                (
                    "httpx",
                    _fetch_with_httpx(
                        url,
                        request.timeout,
                        proxy_url=proxy_url,
                        custom_headers=custom_headers,
                        custom_cookies=custom_cookies,
                    ),
                ),
            )

        race = await _race_strategies(http_coros, url, timeout=10)
        _update_best(race)
        if race.success:
            html, sc, hdrs = _unpack_http_result(race.winner_result)
            raw_html, status_code, response_headers = html, sc, hdrs
            fetched = True
            winning_strategy = (
                "curl_cffi:chrome124"
                if race.winner_name == "curl_cffi_multi"
                else race.winner_name
            )
            winning_tier = 1
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, winning_strategy, 1, True, elapsed_ms)
        else:
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, "tier1", 1, False, elapsed_ms)
            logger.warning(
                f"Tier 1 HTTP failed for {url} (hard={hard_site}, "
                f"best_html={len(race.best_html) if race.best_html else 0} chars, "
                f"elapsed={elapsed_ms:.0f}ms)"
            )

    # === Tier 2: Browser race — race(chromium_stealth, firefox_stealth) ===
    # For hard sites with starting_tier <= 2, combine Tier 2 + Tier 3 into one big race
    # When stealth-engine is available, race it alongside local fallbacks.
    _skip_tier3 = False
    _has_stealth_engine = bool(settings.STEALTH_ENGINE_URL)
    if not fetched and starting_tier <= 2:
        tier_start = time.time()

        if crawl_session:
            # Use persistent CrawlSession — no context creation overhead
            browser_coros = [
                (
                    "chromium_stealth",
                    _fetch_with_browser_session(url, request, crawl_session),
                ),
            ]
            # For hard sites, also race a fresh browser — the crawl session may be
            # flagged by anti-bot systems, so a standalone browser gives a second chance.
            if hard_site:
                browser_coros.append(
                    (
                        "chromium_stealth_fresh",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright),
                    ),
                )
                # Add stealth-engine contestants for hard sites
                if _has_stealth_engine:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                    browser_coros.append((
                        "stealth_firefox",
                        _fetch_via_stealth_engine(url, request, use_firefox=True, proxy=proxy_playwright),
                    ))
                t2_timeout = 35
            else:
                # Non-hard crawl: add stealth-engine Chromium as extra racer
                if _has_stealth_engine:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                t2_timeout = 20
        else:
            if hard_site:
                # Hard sites: full stealth with all anti-detection
                browser_coros = [
                    (
                        "chromium_stealth",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, stealth=True),
                    ),
                    (
                        "firefox_stealth",
                        _fetch_with_browser_stealth(
                            url, request, proxy=proxy_playwright, use_firefox=True, stealth=True
                        ),
                    ),
                ]
                # Add stealth-engine contestants (Patchright + Camoufox)
                if _has_stealth_engine:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                    browser_coros.append((
                        "stealth_firefox",
                        _fetch_via_stealth_engine(url, request, use_firefox=True, proxy=proxy_playwright),
                    ))
                # Race Tier 2 AND Tier 3 concurrently for massive speed win
                if starting_tier <= 3:
                    heavy_coros = [
                        (
                            "google_search_chain",
                            _fetch_with_google_search_chain(
                                url, request, proxy=proxy_playwright
                            ),
                        ),
                        (
                            "advanced_prewarm",
                            _fetch_with_advanced_prewarm(
                                url, request, proxy=proxy_playwright
                            ),
                        ),
                    ]
                    browser_coros.extend(heavy_coros)
                    _skip_tier3 = True
                    t2_timeout = 35  # Combined race timeout
                else:
                    t2_timeout = 30
            else:
                # Non-hard sites: light mode — no stealth scripts, no warm-up
                browser_coros = []
                # Stealth-engine first (preferred — no JS overhead)
                if _has_stealth_engine:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                # Local fallbacks
                browser_coros.append(
                    (
                        "chromium_light",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, stealth=False),
                    ),
                )
                browser_coros.append(
                    (
                        "firefox_light",
                        _fetch_with_browser_stealth(
                            url, request, proxy=proxy_playwright, use_firefox=True, stealth=False
                        ),
                    ),
                )
                t2_timeout = 20

        race = await _race_strategies(
            browser_coros, url, validate_fn=_validate_browser, timeout=t2_timeout
        )
        _update_best(race)
        if race.success:
            (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            ) = _unpack_browser_result(race.winner_result)
            fetched = True
            winning_strategy = race.winner_name
            # Determine correct tier based on which strategy won
            if race.winner_name in ("google_search_chain", "advanced_prewarm"):
                winning_tier = 3
            else:
                winning_tier = 2
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(
                url, winning_strategy, winning_tier, True, elapsed_ms
            )
        else:
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, "tier2", 2, False, elapsed_ms)
            logger.warning(
                f"Tier 2 Browser failed for {url} (hard={hard_site}, "
                f"best_html={len(race.best_html) if race.best_html else 0} chars, "
                f"timeout={t2_timeout}s, elapsed={elapsed_ms:.0f}ms)"
            )

    # === Tier 3: Heavy race (hard sites) — race(google_search, advanced_prewarm) ===
    if not fetched and hard_site and starting_tier <= 3 and not _skip_tier3:
        tier_start = time.time()

        heavy_coros = [
            (
                "google_search_chain",
                _fetch_with_google_search_chain(url, request, proxy=proxy_playwright),
            ),
            (
                "advanced_prewarm",
                _fetch_with_advanced_prewarm(url, request, proxy=proxy_playwright),
            ),
        ]

        race = await _race_strategies(
            heavy_coros, url, validate_fn=_validate_browser, timeout=35
        )
        _update_best(race)
        if race.success:
            (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            ) = _unpack_browser_result(race.winner_result)
            fetched = True
            winning_strategy = race.winner_name
            winning_tier = 3
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, winning_strategy, 3, True, elapsed_ms)
        else:
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, "tier3", 3, False, elapsed_ms)

    # === Tier 4: Fallback parallel — race(google_cache, wayback) ===
    if not fetched:
        tier_start = time.time()

        fallback_coros = [
            (
                "google_cache",
                _fetch_from_google_cache(url, request.timeout, proxy_url=proxy_url),
            ),
            (
                "wayback",
                _fetch_from_wayback_machine(url, request.timeout, proxy_url=proxy_url),
            ),
        ]

        def _validate_fallback(result):
            html = result[0] if isinstance(result, tuple) else result
            return bool(html) and len(html) > 500 and not _looks_blocked(html)

        race = await _race_strategies(
            fallback_coros, url, validate_fn=_validate_fallback, timeout=12
        )
        _update_best(race)
        if race.success:
            html, sc, hdrs = _unpack_http_result(race.winner_result)
            raw_html, status_code, response_headers = html, sc, hdrs
            fetched = True
            winning_strategy = race.winner_name
            winning_tier = 4
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, winning_strategy, 4, True, elapsed_ms)

    # --- Final fallback: use best available content even if blocked ---
    if not fetched:
        if raw_html_best:
            raw_html = raw_html_best
            # Recover screenshot from browser race that had content but failed validation
            if not screenshot_b64 and screenshot_b64_best:
                screenshot_b64 = screenshot_b64_best
                action_screenshots = action_screenshots_best
            logger.warning(
                f"All tiers failed for {url}, using best available ({len(raw_html_best)} chars)"
            )
        elif raw_html and _looks_blocked(raw_html):
            if not screenshot_b64 and screenshot_b64_best:
                screenshot_b64 = screenshot_b64_best
                action_screenshots = action_screenshots_best
            logger.warning(
                f"All tiers failed for {url}, using last result ({len(raw_html)} chars)"
            )
        else:
            logger.error(
                f"All tiers failed for {url} — no content retrieved at all "
                f"(hard_site={hard_site}, starting_tier={starting_tier}, "
                f"best_html={len(raw_html_best) if raw_html_best else 0} chars)"
            )
            duration = time.time() - start_time
            scrape_duration_seconds.observe(duration)
            return ScrapeData(
                metadata=PageMetadata(source_url=url, status_code=status_code or 0),
            )

    if not raw_html:
        logger.error(
            f"No raw_html for {url} despite fallback (best={len(raw_html_best)})"
        )
        duration = time.time() - start_time
        scrape_duration_seconds.observe(duration)
        return ScrapeData(
            metadata=PageMetadata(source_url=url, status_code=status_code or 0),
        )

    # === Fallback screenshot: render HTML in browser if we have content but no screenshot ===
    if "screenshot" in request.formats and not screenshot_b64 and raw_html:
        try:
            async with browser_pool.get_page(target_url=url) as page:
                await page.set_content(raw_html, wait_until="domcontentloaded")
                await page.wait_for_timeout(500)
                screenshot_bytes = await page.screenshot(
                    type="jpeg", quality=80, full_page=True
                )
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                logger.info(f"Fallback screenshot rendered for {url}")
        except Exception as e:
            logger.debug(f"Fallback screenshot failed for {url}: {e}")

    # === Parallel content extraction ===
    result_data: dict[str, Any] = {}
    _extract_start = time.time()

    # Fast path: combined extraction + markdown in single parse (saves ~200-350ms)
    loop = asyncio.get_running_loop()
    extraction_futures = []
    extraction_keys = []

    if "markdown" in request.formats:
        # extract_and_convert does extraction + markdown in 1 parse instead of 3
        clean_html, markdown_result = await loop.run_in_executor(
            _extraction_executor,
            extract_and_convert,
            raw_html,
            url,
            request.only_main_content,
            request.include_tags,
            request.exclude_tags,
        )
        result_data["markdown"] = markdown_result
    else:
        clean_html = (
            extract_main_content(raw_html, url)
            if request.only_main_content
            else raw_html
        )
        if request.include_tags or request.exclude_tags:
            clean_html = apply_tag_filters(
                clean_html, request.include_tags, request.exclude_tags
            )
    if "links" in request.formats:
        extraction_futures.append(
            loop.run_in_executor(_extraction_executor, extract_links, raw_html, url)
        )
        extraction_keys.append("links")
        extraction_futures.append(
            loop.run_in_executor(
                _extraction_executor, extract_links_detailed, raw_html, url
            )
        )
        extraction_keys.append("links_detail")
    if "structured_data" in request.formats:
        extraction_futures.append(
            loop.run_in_executor(
                _extraction_executor, extract_structured_data, raw_html
            )
        )
        extraction_keys.append("structured_data")
    if "headings" in request.formats:
        extraction_futures.append(
            loop.run_in_executor(_extraction_executor, extract_headings, raw_html)
        )
        extraction_keys.append("headings")
    if "images" in request.formats:
        extraction_futures.append(
            loop.run_in_executor(_extraction_executor, extract_images, raw_html, url)
        )
        extraction_keys.append("images")

    # metadata extraction always runs — guard against None response_headers
    extraction_futures.append(
        loop.run_in_executor(
            _extraction_executor,
            extract_metadata,
            raw_html,
            url,
            status_code,
            response_headers or {},
        )
    )
    extraction_keys.append("_metadata")

    # Await all extractions concurrently
    if extraction_futures:
        extraction_results = await asyncio.gather(*extraction_futures)
        for key, value in zip(extraction_keys, extraction_results):
            if key == "_metadata":
                continue
            result_data[key] = value
        # metadata is always the last one
        metadata_dict = extraction_results[-1]
    else:
        metadata_dict = extract_metadata(raw_html, url, status_code, response_headers)

    _extract_elapsed = (time.time() - _extract_start) * 1000
    _fetch_elapsed = (_extract_start - start_time) * 1000
    _total_elapsed = (time.time() - start_time) * 1000
    logger.info(
        f"[TIMING] {url} — fetch: {_fetch_elapsed:.0f}ms, "
        f"extract: {_extract_elapsed:.0f}ms, total: {_total_elapsed:.0f}ms "
        f"(tier={winning_tier}, strategy={winning_strategy}, html={len(raw_html)}b)"
    )

    if "html" in request.formats:
        result_data["html"] = clean_html
    if "raw_html" in request.formats:
        result_data["raw_html"] = raw_html
    if "screenshot" in request.formats:
        if screenshot_b64:
            result_data["screenshot"] = screenshot_b64
        elif action_screenshots:
            result_data["screenshot"] = action_screenshots[-1]

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

    # Circuit breaker — record success/failure (skip hard sites)
    if domain and not _is_hard_site(url):
        if fetched:
            try:
                from app.services.circuit_breaker import record_success

                await record_success(domain)
            except Exception:
                pass
        else:
            try:
                from app.services.circuit_breaker import record_failure

                await record_failure(domain)
            except Exception:
                pass

    duration = time.time() - start_time
    scrape_duration_seconds.observe(duration)
    logger.info(
        f"Scraped {url} in {duration:.1f}s (tier={winning_tier}, strategy={winning_strategy})"
    )
    return scrape_data


def classify_error(
    error: str | None, html: str | None = None, status_code: int = 0
) -> str | None:
    """Classify a scrape failure into a structured error code.

    Returns one of: BLOCKED_BY_WAF, CAPTCHA_REQUIRED, TIMEOUT, JS_REQUIRED,
    NETWORK_ERROR, or None if no specific classification applies.
    """
    if not error and not html:
        return None

    err_lower = (error or "").lower()

    # Timeout errors
    if any(kw in err_lower for kw in ("timeout", "timed out", "timedout")):
        return "TIMEOUT"

    # Network errors
    if any(
        kw in err_lower
        for kw in (
            "connection",
            "dns",
            "resolve",
            "refused",
            "unreachable",
            "network",
            "ssl",
            "certificate",
            "eof",
        )
    ):
        return "NETWORK_ERROR"

    # Check HTML content for specific block patterns
    html_lower = (html or "").lower()
    if any(
        kw in html_lower
        for kw in (
            "captcha",
            "recaptcha",
            "hcaptcha",
            "verify you are human",
            "verify you're human",
        )
    ):
        return "CAPTCHA_REQUIRED"

    if any(
        kw in html_lower
        for kw in (
            "access denied",
            "blocked",
            "403 forbidden",
            "cloudflare",
            "performance & security by",
            "sucuri",
            "incapsula",
            "datadome",
            "perimeterx",
        )
    ):
        return "BLOCKED_BY_WAF"

    if status_code == 403 or status_code == 451:
        return "BLOCKED_BY_WAF"

    if any(
        kw in html_lower
        for kw in (
            "javascript is disabled",
            "enable javascript",
            "requires javascript",
            "javascript is required",
        )
    ):
        return "JS_REQUIRED"

    # All strategies failed = likely blocked
    if "all scraping strategies failed" in err_lower:
        return "BLOCKED_BY_WAF"

    return None


def get_block_reason(html: str | None, status_code: int = 0) -> str:
    """Return a human-readable block reason based on HTML content and status code."""
    html_lower = (html or "").lower()

    if status_code == 429:
        return "Rate limited (429) — the target site is throttling requests. Try again later or use a proxy."

    if any(
        kw in html_lower
        for kw in (
            "cloudflare",
            "performance & security by",
            "ray id",
            "checking your browser",
        )
    ):
        return (
            "Blocked by Cloudflare WAF — the site is using Cloudflare bot protection."
        )

    if any(
        kw in html_lower
        for kw in (
            "captcha",
            "recaptcha",
            "hcaptcha",
            "verify you are human",
            "verify you're human",
        )
    ):
        return "CAPTCHA detected — the site requires human verification. Try using a browser-based strategy or proxy."

    if "datadome" in html_lower:
        return "Blocked by DataDome — the site uses DataDome bot detection."

    if "perimeterx" in html_lower:
        return "Blocked by PerimeterX — the site uses PerimeterX bot detection."

    if "sucuri" in html_lower:
        return "Blocked by Sucuri WAF — the site uses Sucuri firewall protection."

    if "incapsula" in html_lower:
        return "Blocked by Imperva/Incapsula — the site uses Imperva bot management."

    if any(
        kw in html_lower
        for kw in (
            "akamai",
            "your connection needs to be verified",
            "connection is being verified",
        )
    ):
        return "Blocked by Akamai Bot Manager — the site uses Akamai bot protection."

    if (
        status_code == 403
        or "access denied" in html_lower
        or "403 forbidden" in html_lower
    ):
        return "Access denied (403) — the site explicitly blocked the request."

    if status_code == 451:
        return (
            "Unavailable for legal reasons (451) — content restricted in your region."
        )

    if any(
        kw in html_lower
        for kw in ("javascript is disabled", "enable javascript", "requires javascript")
    ):
        return "JavaScript required — the site needs JavaScript execution. A browser-based strategy may work."

    return "All scraping strategies failed — the site may be using advanced bot protection. Try enabling proxy rotation."


# ---------------------------------------------------------------------------
# Document handling (PDF, DOCX, XLSX, PPTX, CSV, RTF, EPUB)
# ---------------------------------------------------------------------------


async def _handle_document_url(
    url: str,
    doc_type: str,
    request: ScrapeRequest,
    proxy_manager,
    start_time: float,
) -> ScrapeData:
    """Fetch and extract content from document URLs."""
    from app.core.metrics import scrape_duration_seconds
    from app.services.document import extract_document, detect_document_type

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
                kwargs: dict[str, Any] = {
                    "timeout": request.timeout / 1000,
                    "allow_redirects": True,
                }
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

    if actual_type in ("pdf", "docx", "xlsx", "pptx", "csv", "rtf", "epub"):
        doc_result = await extract_document(raw_bytes, actual_type)
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
        structured_data={"document_metadata": doc_result.metadata}
        if "structured_data" in request.formats
        else None,
    )


# ---------------------------------------------------------------------------
# Strategy 1: curl_cffi — multi-profile TLS fingerprint impersonation
# ---------------------------------------------------------------------------


async def _fetch_with_curl_cffi_single(
    url: str,
    timeout: int,
    profile: str = "chrome124",
    proxy_url: str | None = None,
    custom_headers: dict[str, str] | None = None,
    custom_cookies: dict[str, str] | None = None,
) -> tuple[str, int, dict[str, str]]:
    """HTTP fetch with a single TLS fingerprint profile (pooled session)."""
    timeout_seconds = timeout / 1000
    headers = _get_headers_for_profile(profile, url)
    if custom_headers:
        headers.update(custom_headers)

    cookie_str = ""
    if custom_cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in custom_cookies.items())
        headers["Cookie"] = cookie_str

    if proxy_url:
        # Proxied requests use fresh sessions
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate=profile) as session:
            kwargs: dict[str, Any] = dict(
                timeout=timeout_seconds,
                allow_redirects=True,
                headers=headers,
                proxy=proxy_url,
            )
            response = await session.get(url, **kwargs)
    else:
        session = _get_curl_session(profile)
        kwargs: dict[str, Any] = dict(
            timeout=timeout_seconds, allow_redirects=True, headers=headers
        )
        response = await session.get(url, **kwargs)

    resp_headers = {k.lower(): v for k, v in response.headers.items()}
    return response.text or "", response.status_code, resp_headers


async def _fetch_with_curl_cffi_multi(
    url: str,
    timeout: int,
    proxy_url: str | None = None,
    custom_headers: dict[str, str] | None = None,
    custom_cookies: dict[str, str] | None = None,
) -> tuple[str, int, dict[str, str]]:
    """HTTP fetch racing 3 TLS fingerprints concurrently (batch 1), then 2 more if needed."""

    # Batch 1: race first 3 profiles concurrently
    batch1 = _CURL_CFFI_PROFILES[:3]
    batch1_coros = [
        (
            f"curl_cffi:{p}",
            _fetch_with_curl_cffi_single(
                url,
                timeout,
                profile=p,
                proxy_url=proxy_url,
                custom_headers=custom_headers,
                custom_cookies=custom_cookies,
            ),
        )
        for p in batch1
    ]

    def _validate_http(result):
        html, sc, _ = result
        return bool(html) and sc < 400 and not _looks_blocked(html)

    best_html = ""
    best_result = ("", 0, {})

    race = await _race_strategies(
        batch1_coros, url, validate_fn=_validate_http, timeout=10
    )
    if race.success:
        logger.info(
            f"{race.winner_name} succeeded for {url} ({len(race.winner_result[0])} chars)"
        )
        return race.winner_result
    if race.best_html and len(race.best_html) > len(best_html):
        best_html = race.best_html
        best_result = race.best_result

    # Batch 2: race remaining 2 profiles
    batch2 = _CURL_CFFI_PROFILES[3:]
    if batch2:
        batch2_coros = [
            (
                f"curl_cffi:{p}",
                _fetch_with_curl_cffi_single(
                    url,
                    timeout,
                    profile=p,
                    proxy_url=proxy_url,
                    custom_headers=custom_headers,
                    custom_cookies=custom_cookies,
                ),
            )
            for p in batch2
        ]

        race = await _race_strategies(
            batch2_coros, url, validate_fn=_validate_http, timeout=10
        )
        if race.success:
            logger.info(
                f"{race.winner_name} succeeded for {url} ({len(race.winner_result[0])} chars)"
            )
            return race.winner_result
        if race.best_html and len(race.best_html) > len(best_html):
            best_result = race.best_result

    return best_result


# ---------------------------------------------------------------------------
# Strategy 2: httpx with HTTP/2 + header rotation
# ---------------------------------------------------------------------------


async def _fetch_with_httpx(
    url: str,
    timeout: int,
    proxy_url: str | None = None,
    custom_headers: dict[str, str] | None = None,
    custom_cookies: dict[str, str] | None = None,
) -> tuple[str, int, dict[str, str]]:
    timeout_seconds = timeout / 1000
    headers = random.choice(_HEADER_ROTATION_POOL).copy()
    if custom_headers:
        headers.update(custom_headers)

    cookies_kwarg = custom_cookies if custom_cookies else None

    if proxy_url:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers=headers,
            http2=True,
            proxy=proxy_url,
        ) as client:
            response = await client.get(url, cookies=cookies_kwarg)
    else:
        client = await _get_httpx_client()
        response = await client.get(
            url, headers=headers, timeout=timeout_seconds, cookies=cookies_kwarg
        )

    resp_headers = {k.lower(): v for k, v in response.headers.items()}
    return response.text, response.status_code, resp_headers


# ---------------------------------------------------------------------------
# Strategy: Cookie-enhanced HTTP (uses browser cookies with curl_cffi)
# ---------------------------------------------------------------------------


async def _fetch_with_cookie_http(
    url: str,
    timeout: int,
    cookies: list[dict],
    proxy_url: str | None = None,
) -> tuple[str, int, dict[str, str]]:
    """HTTP fetch using cookies harvested from browser sessions."""
    if not cookies:
        return "", 0, {}

    # Build cookie header string from Playwright cookie format
    cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value")
    )
    if not cookie_header:
        return "", 0, {}

    timeout_seconds = timeout / 1000
    headers = _get_headers_for_profile("chrome124", url)
    headers["Cookie"] = cookie_header

    if proxy_url:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate="chrome124") as session:
            kwargs: dict[str, Any] = dict(
                timeout=timeout_seconds,
                allow_redirects=True,
                headers=headers,
                proxy=proxy_url,
            )
            response = await session.get(url, **kwargs)
    else:
        session = _get_curl_session("chrome124")
        kwargs: dict[str, Any] = dict(
            timeout=timeout_seconds, allow_redirects=True, headers=headers
        )
        response = await session.get(url, **kwargs)

    resp_headers = {k.lower(): v for k, v in response.headers.items()}
    resp_headers["x-webharvest-strategy"] = "cookie_http"
    return response.text, response.status_code, resp_headers


# ---------------------------------------------------------------------------
# Strategy 3/4: Browser with stealth + request interception + warm-up
# ---------------------------------------------------------------------------


async def _fetch_with_browser_stealth(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
    use_firefox: bool = False,
    stealth: bool = True,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Fast browser fetch: domcontentloaded + short networkidle + request interception.

    When stealth=False (light mode), skips stealth scripts, warm-up navigation,
    and human-like interactions for faster page loads on non-hard sites.
    """
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    async with browser_pool.get_page(
        proxy=proxy, use_firefox=use_firefox, target_url=url, stealth=stealth
    ) as page:
        # Mobile viewport emulation (device preset or default iPhone 14)
        if getattr(request, "mobile", False) or getattr(request, "mobile_device", None):
            from app.services.mobile_presets import get_device_preset

            preset = get_device_preset(getattr(request, "mobile_device", None))
            if not preset:
                preset = {
                    "width": 390,
                    "height": 844,
                    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                }
            await page.set_viewport_size(
                {"width": preset["width"], "height": preset["height"]}
            )
            await page.set_extra_http_headers({"User-Agent": preset["user_agent"]})

        # Inject custom cookies before navigation
        if getattr(request, "cookies", None):
            from urllib.parse import urlparse as _urlparse

            _domain = _urlparse(url).netloc
            await page.context.add_cookies(
                [
                    {"name": k, "value": v, "domain": _domain, "path": "/"}
                    for k, v in request.cookies.items()
                ]
            )

        # Inject custom headers
        if getattr(request, "headers", None):
            await page.set_extra_http_headers(request.headers)

        # Set up request interception (blocks third-party bot detection on hard sites)
        if stealth:
            await _setup_request_interception(page, url)

        referrer = random.choice(_GOOGLE_REFERRERS) if stealth else None
        hard_site = _is_hard_site(url)

        # Warm-up navigation for hard sites: visit homepage first to build session
        # Skip if we already have cookies for this domain (saves 1.5-3s)
        # Also skip entirely in light mode (stealth=False)
        if hard_site and stealth:
            domain = browser_pool._get_domain(url)
            has_cookies = domain in browser_pool._cookie_jar
            homepage = _get_homepage(url)
            if homepage and not has_cookies:
                try:
                    await page.goto(
                        homepage,
                        wait_until="domcontentloaded",
                        timeout=8000,
                        referer=referrer,
                    )
                    await page.wait_for_timeout(random.randint(800, 1500))
                    # Human-like interaction during warm-up
                    vp = page.viewport_size or {"width": 1920, "height": 1080}
                    await page.mouse.move(
                        random.randint(200, vp["width"] - 200),
                        random.randint(150, vp["height"] - 200),
                        steps=random.randint(8, 15),
                    )
                    await page.mouse.wheel(0, random.randint(200, 500))
                    await page.wait_for_timeout(random.randint(200, 400))
                    await _try_accept_cookies(page)
                    await page.wait_for_timeout(random.randint(200, 400))
                except Exception:
                    pass  # Best-effort warm-up

        # Fast navigation: domcontentloaded first (doesn't hang on analytics)
        goto_kwargs = {
            "wait_until": "domcontentloaded",
            "timeout": 15000,
        }
        if referrer:
            goto_kwargs["referer"] = referrer
        response = await page.goto(url, **goto_kwargs)
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        # Networkidle — give JS time to render
        # Light mode: 3s, hard sites: 6s, normal stealth: 3s
        _idle_timeout = 3000
        if hard_site and stealth:
            _idle_timeout = 6000
        try:
            await page.wait_for_load_state("networkidle", timeout=_idle_timeout)
        except Exception:
            pass

        # Doc framework detection: if this is a doc site (GitBook, Docusaurus, etc.),
        # wait for the content-specific selectors instead of blind timers
        _doc_fw = await _wait_for_doc_content(page, timeout_ms=5000)
        if _doc_fw:
            logger.debug(f"Doc framework '{_doc_fw}' detected for {url}, content ready")

        if hard_site and stealth:
            # Human-like interaction after page load
            await page.wait_for_timeout(random.randint(500, 1000))
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            await page.mouse.move(
                random.randint(200, vp["width"] - 200),
                random.randint(150, vp["height"] - 200),
                steps=random.randint(8, 15),
            )
            await page.mouse.wheel(0, random.randint(300, 600))
            await page.wait_for_timeout(random.randint(200, 400))
            await _try_accept_cookies(page)

            # Challenge re-check: Akamai/PerimeterX may serve a challenge that
            # resolves after JS execution. Wait and re-check up to 2 times.
            for _retry in range(2):
                html_check = await page.content()
                if not _looks_blocked(html_check):
                    break
                logger.debug(
                    f"Challenge detected on {url}, waiting for resolution (attempt {_retry + 1})"
                )
                await page.wait_for_timeout(random.randint(1500, 2500))
                # Interact to help solve visual challenges
                await page.mouse.move(
                    random.randint(200, vp["width"] - 200),
                    random.randint(150, vp["height"] - 200),
                    steps=random.randint(8, 15),
                )
        elif stealth:
            await page.wait_for_timeout(random.randint(100, 250))
        else:
            # Light mode: still need a brief wait for SPAs to hydrate
            await page.wait_for_timeout(500)

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=True
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers


async def _fetch_with_browser_session(
    url: str,
    request: ScrapeRequest,
    crawl_session,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Browser fetch reusing a persistent CrawlSession context."""
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}
    raw_html = ""

    page = None
    try:
        page = await crawl_session.new_page()
    except Exception as e:
        logger.debug(f"CrawlSession.new_page() failed for {url}: {e}")
        raise

    try:
        # Mobile viewport emulation (device preset or default iPhone 14)
        if getattr(request, "mobile", False) or getattr(request, "mobile_device", None):
            from app.services.mobile_presets import get_device_preset

            preset = get_device_preset(getattr(request, "mobile_device", None))
            if not preset:
                preset = {
                    "width": 390,
                    "height": 844,
                    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                }
            await page.set_viewport_size(
                {"width": preset["width"], "height": preset["height"]}
            )
            await page.set_extra_http_headers({"User-Agent": preset["user_agent"]})

        # Inject custom cookies
        if getattr(request, "cookies", None):
            from urllib.parse import urlparse as _urlparse

            _domain = _urlparse(url).netloc
            await page.context.add_cookies(
                [
                    {"name": k, "value": v, "domain": _domain, "path": "/"}
                    for k, v in request.cookies.items()
                ]
            )

        # Inject custom headers
        if getattr(request, "headers", None):
            await page.set_extra_http_headers(request.headers)

        await _setup_request_interception(page, url)

        referrer = random.choice(_GOOGLE_REFERRERS)
        hard_site = _is_hard_site(url)

        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=15000,
            referer=referrer,
        )
        status_code = response.status if response else 0
        if response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}

        try:
            await page.wait_for_load_state(
                "networkidle", timeout=6000 if hard_site else 3000
            )
        except Exception:
            pass

        if hard_site:
            await page.wait_for_timeout(random.randint(500, 1000))
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            await page.mouse.move(
                random.randint(200, vp["width"] - 200),
                random.randint(150, vp["height"] - 200),
                steps=random.randint(8, 15),
            )
            await page.mouse.wheel(0, random.randint(300, 600))
            await page.wait_for_timeout(random.randint(200, 400))

            # Challenge re-check for Akamai/PerimeterX
            for _retry in range(2):
                html_check = await page.content()
                if not _looks_blocked(html_check):
                    break
                await page.wait_for_timeout(random.randint(1500, 2500))
                await page.mouse.move(
                    random.randint(200, vp["width"] - 200),
                    random.randint(150, vp["height"] - 200),
                    steps=random.randint(8, 15),
                )
        else:
            await page.wait_for_timeout(random.randint(100, 250))

        await _try_accept_cookies(page)

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=True
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()
    except Exception as e:
        # Catch TargetClosedError from race cancellation — clean up page safely
        # then re-raise so the race treats this as a failed strategy.
        if page:
            try:
                await crawl_session.close_page(page)
            except Exception:
                pass
            page = None  # Prevent double-close in finally
        raise
    finally:
        if page:
            try:
                await crawl_session.close_page(page)
            except Exception:
                pass

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers


# ---------------------------------------------------------------------------
# Strategy 5: Google Search referrer chain
# ---------------------------------------------------------------------------


async def _fetch_with_google_search_chain(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Navigate to target via Google search results for organic referrer chain."""
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Build search query
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if path_parts:
        last_segment = path_parts[-1].replace("-", " ").replace("_", " ")
        query = f"site:{domain} {last_segment}"
    else:
        query = domain

    async with browser_pool.get_page(proxy=proxy, target_url=url) as page:
        await _setup_request_interception(page, url)

        # 1. Navigate to Google
        try:
            await page.goto(
                "https://www.google.com/", wait_until="domcontentloaded", timeout=10000
            )
        except Exception:
            # Google blocked too — fall back to direct navigation
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
            raw_html = await page.content()
            return (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            )

        await page.wait_for_timeout(random.randint(500, 1000))

        # 2. Accept Google consent (GDPR)
        await _try_accept_google_consent(page)

        # 3. Type search query character-by-character with human-like delays
        search_input = await page.query_selector("textarea[name='q'], input[name='q']")
        if not search_input:
            # Fallback: direct navigation
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
            raw_html = await page.content()
            return (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            )

        await search_input.click()
        for char in query:
            await search_input.type(char, delay=random.randint(30, 80))
            if random.random() < 0.05:  # Reduced pause probability
                await page.wait_for_timeout(random.randint(150, 350))

        await page.wait_for_timeout(random.randint(200, 500))
        await page.keyboard.press("Enter")

        # 4. Wait for results
        try:
            await page.wait_for_selector("#search", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(random.randint(500, 1000))

        # 5. Find and click link matching target domain
        links = await page.query_selector_all(f"a[href*='{domain}']")
        clicked = False
        for link in links[:5]:
            try:
                href = await link.get_attribute("href")
                if href and domain in href:
                    # Scroll into view
                    await link.scroll_into_view_if_needed()
                    await page.wait_for_timeout(random.randint(300, 600))

                    # Move mouse naturally to the link
                    box = await link.bounding_box()
                    if box:
                        target_x = box["x"] + box["width"] / 2 + random.randint(-10, 10)
                        target_y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
                        await page.mouse.move(
                            target_x, target_y, steps=random.randint(10, 20)
                        )
                        await page.wait_for_timeout(random.randint(100, 300))

                    await link.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # Direct navigation as fallback
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        else:
            # Wait for navigation after click
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

        await page.wait_for_timeout(random.randint(500, 1000))
        await _try_accept_cookies(page)

        # 6. If landed on domain but not exact page, navigate internally
        current_url = page.url
        if domain in current_url and current_url != url:
            try:
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=15000
                )
                status_code = response.status if response else 0
                if response:
                    response_headers = {
                        k.lower(): v for k, v in response.headers.items()
                    }
                await page.wait_for_timeout(random.randint(500, 1000))
            except Exception:
                pass

        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass

        await _try_accept_cookies(page)

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=True
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()
        if not status_code:
            status_code = 200 if raw_html and len(raw_html) > 500 else 0

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers


# ---------------------------------------------------------------------------
# Strategy 6: Advanced session pre-warming
# ---------------------------------------------------------------------------


async def _fetch_with_advanced_prewarm(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """
    Full pre-warming: Google session → search & click-through → browse naturally → target.
    Creates an organic referrer chain that mimics a real user journey.
    """
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Build a natural search term for the site
    site_name = domain.split(".")[0].title()
    tld_parts = domain.split(".")
    if len(tld_parts) > 2:
        country_map = {
            "in": "india",
            "uk": "uk",
            "de": "germany",
            "fr": "france",
            "jp": "japan",
            "ca": "canada",
            "au": "australia",
            "es": "spain",
            "it": "italy",
        }
        country = country_map.get(tld_parts[-1], tld_parts[-1])
        search_term = f"{site_name} {country}"
    else:
        search_term = site_name

    async with browser_pool.get_page(proxy=proxy, target_url=url) as page:
        await _setup_request_interception(page, url)

        # --- Phase 1: Google session ---
        try:
            await page.goto(
                "https://www.google.com/", wait_until="domcontentloaded", timeout=10000
            )
            await page.wait_for_timeout(random.randint(500, 1000))

            await _try_accept_google_consent(page)

            # Brief mouse interaction on Google (builds cookies)
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            for _ in range(2):
                await page.mouse.move(
                    random.randint(200, vp["width"] - 200),
                    random.randint(100, vp["height"] - 200),
                    steps=random.randint(8, 15),
                )
                await page.wait_for_timeout(random.randint(100, 200))
        except Exception:
            pass

        # --- Phase 2: Search & click-through ---
        try:
            search_input = await page.query_selector(
                "textarea[name='q'], input[name='q']"
            )
            if search_input:
                await search_input.click()
                for char in search_term:
                    await search_input.type(char, delay=random.randint(30, 80))
                    if random.random() < 0.05:
                        await page.wait_for_timeout(random.randint(150, 350))

                await page.wait_for_timeout(random.randint(200, 400))
                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_selector("#search", timeout=8000)
                except Exception:
                    pass
                await page.wait_for_timeout(random.randint(500, 1000))

                # Click first matching result
                links = await page.query_selector_all(f"a[href*='{domain}']")
                for link in links[:5]:
                    try:
                        href = await link.get_attribute("href")
                        if href and domain in href:
                            await link.scroll_into_view_if_needed()
                            await page.wait_for_timeout(random.randint(300, 600))
                            box = await link.bounding_box()
                            if box:
                                await page.mouse.move(
                                    box["x"]
                                    + box["width"] / 2
                                    + random.randint(-10, 10),
                                    box["y"]
                                    + box["height"] / 2
                                    + random.randint(-3, 3),
                                    steps=random.randint(10, 20),
                                )
                            await link.click()
                            try:
                                await page.wait_for_load_state(
                                    "domcontentloaded", timeout=15000
                                )
                            except Exception:
                                pass
                            break
                    except Exception:
                        continue
        except Exception:
            pass

        await page.wait_for_timeout(random.randint(500, 1000))
        await _try_accept_cookies(page)

        # --- Phase 3: Browse naturally (1-2 internal pages, reduced delays) ---
        current = page.url
        if domain in current:
            try:
                vp = page.viewport_size or {"width": 1920, "height": 1080}
                for _ in range(random.randint(1, 2)):
                    # Mouse movements
                    for _ in range(random.randint(1, 2)):
                        await page.mouse.move(
                            random.randint(100, vp["width"] - 100),
                            random.randint(100, vp["height"] - 100),
                            steps=random.randint(8, 15),
                        )
                        await page.wait_for_timeout(random.randint(150, 300))

                    # Scroll
                    await page.mouse.wheel(0, random.randint(200, 500))
                    await page.wait_for_timeout(random.randint(150, 300))

                    # Click a random internal link
                    internal_links = await page.query_selector_all(
                        f"a[href*='{domain}']"
                    )
                    if internal_links:
                        link = random.choice(internal_links[:10])
                        try:
                            await link.scroll_into_view_if_needed()
                            await page.wait_for_timeout(random.randint(80, 150))
                            await link.click()
                            await page.wait_for_load_state(
                                "domcontentloaded", timeout=8000
                            )
                        except Exception:
                            pass

                    await page.wait_for_timeout(random.randint(200, 400))
                    await _try_accept_cookies(page)
            except Exception:
                pass

        # --- Phase 4: Navigate to actual target URL ---
        try:
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # Final human interaction
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        for _ in range(random.randint(2, 3)):
            await page.mouse.move(
                random.randint(100, vp["width"] - 100),
                random.randint(100, vp["height"] - 100),
                steps=random.randint(8, 15),
            )
            await page.wait_for_timeout(random.randint(100, 200))

        await _try_accept_cookies(page)

        # Challenge re-check loop
        for _ in range(2):
            html_check = await page.content()
            if not _looks_blocked(html_check):
                break
            await page.wait_for_timeout(random.randint(1500, 2500))

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(
                type="jpeg", quality=80, full_page=True
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        raw_html = await page.content()

    return raw_html, status_code, screenshot_b64, action_screenshots, response_headers


# ---------------------------------------------------------------------------
# Strategy 7: Google Cache fallback
# ---------------------------------------------------------------------------


async def _fetch_from_google_cache(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    """Fetch content from Google's cache — bypasses all site-level protection."""
    cache_url = (
        f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}"
    )
    timeout_seconds = timeout / 1000

    cache_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
    }

    if proxy_url:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate="chrome124") as session:
            kwargs: dict[str, Any] = dict(
                timeout=timeout_seconds,
                allow_redirects=True,
                headers=cache_headers,
                proxy=proxy_url,
            )
            response = await session.get(cache_url, **kwargs)
    else:
        session = _get_curl_session("chrome124")
        kwargs: dict[str, Any] = dict(
            timeout=timeout_seconds, allow_redirects=True, headers=cache_headers
        )
        response = await session.get(cache_url, **kwargs)

    html = response.text or ""

    if not html or response.status_code >= 400:
        return "", response.status_code, {}

    html = _strip_google_cache_banner(html)

    if len(html.strip()) < 500:
        return "", response.status_code, {}

    if _looks_blocked(html):
        return "", response.status_code, {}

    resp_headers = {k.lower(): v for k, v in response.headers.items()}
    resp_headers["x-webharvest-source"] = "google-cache"
    return html, response.status_code, resp_headers


# ---------------------------------------------------------------------------
# Strategy 8: Wayback Machine fallback
# ---------------------------------------------------------------------------


async def _fetch_from_wayback_machine(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    """Fetch from Wayback Machine — last resort, content may be stale."""
    timeout_seconds = timeout / 1000

    if proxy_url:
        client = httpx.AsyncClient(
            follow_redirects=True, timeout=timeout_seconds, proxy=proxy_url
        )
        _close_client = True
    else:
        client = await _get_httpx_client()
        _close_client = False

    try:
        # 1. Check availability
        api_url = f"https://archive.org/wayback/available?url={quote_plus(url)}&timestamp=20260219"
        resp = await client.get(api_url, timeout=timeout_seconds)
        if resp.status_code != 200:
            return "", 0, {}

        data = resp.json()
        snapshots = data.get("archived_snapshots", {})
        closest = snapshots.get("closest", {})
        if not closest.get("available"):
            return "", 0, {}

        snapshot_url = closest["url"]
        # Use id_ modifier for raw content without Wayback toolbar
        if "/web/" in snapshot_url:
            parts = snapshot_url.split("/web/", 1)
            ts_and_url = parts[1]
            slash_idx = ts_and_url.find("/")
            if slash_idx > 0:
                ts = ts_and_url[:slash_idx]
                rest = ts_and_url[slash_idx:]
                snapshot_url = f"{parts[0]}/web/{ts}id_{rest}"

        # 2. Fetch snapshot
        resp2 = await client.get(snapshot_url)
        if resp2.status_code >= 400 or not resp2.text:
            return "", resp2.status_code, {}

        html = _strip_wayback_toolbar(resp2.text)

        resp_headers = {k.lower(): v for k, v in resp2.headers.items()}
        resp_headers["x-webharvest-source"] = "wayback-machine"
        return html, 200, resp_headers
    finally:
        if _close_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# Split functions for pipeline extraction (crawl mode)
# ---------------------------------------------------------------------------


async def scrape_url_fetch_only(
    request: ScrapeRequest,
    proxy_manager=None,
    crawl_session=None,
    pinned_strategy: str | None = None,
    pinned_tier: int | None = None,
) -> dict | None:
    """Fetch phase only — returns raw HTML + metadata without content extraction.

    Returns dict with keys: raw_html, status_code, response_headers, screenshot_b64,
    action_screenshots, winning_strategy, winning_tier. Returns None on total failure.

    When pinned_strategy/pinned_tier are set (from a previous crawl page success),
    tries the pinned strategy first before falling through to the normal tier cascade.
    """
    from app.services.document import detect_document_type

    url = request.url
    start_time = time.time()

    # Check if URL points to a document — delegate to full scrape_url for these
    doc_type = detect_document_type(url, content_type=None, raw_bytes=b"")
    if doc_type in ("pdf", "docx", "xlsx", "pptx", "csv", "rtf", "epub"):
        return None  # Caller should fall back to scrape_url()

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
        request.actions or "screenshot" in request.formats or request.wait_for > 0
    )

    fetched = False
    winning_strategy = None
    winning_tier = None

    strategy_data = await get_domain_strategy(url)
    starting_tier = get_starting_tier(strategy_data, hard_site)

    # Custom headers/cookies for HTTP strategies
    _custom_h = getattr(request, "headers", None)
    _custom_c = getattr(request, "cookies", None)

    # === Pinned strategy fast-path (crawl mode) ===
    # When a previous crawl page succeeded with a specific strategy,
    # try it first before the full tier cascade.
    _is_stealth_pinned = pinned_strategy in ("stealth_chromium", "stealth_firefox")
    if pinned_strategy and (not needs_browser or _is_stealth_pinned):
        tier_start = time.time()
        try:
            if pinned_strategy.startswith("curl_cffi:"):
                profile = pinned_strategy.split(":", 1)[1]
                result = await _fetch_with_curl_cffi_single(
                    url,
                    request.timeout,
                    profile=profile,
                    proxy_url=proxy_url,
                    custom_headers=_custom_h,
                    custom_cookies=_custom_c,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = pinned_strategy
                    winning_tier = pinned_tier
            elif pinned_strategy == "httpx":
                result = await _fetch_with_httpx(
                    url,
                    request.timeout,
                    proxy_url=proxy_url,
                    custom_headers=_custom_h,
                    custom_cookies=_custom_c,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = pinned_strategy
                    winning_tier = pinned_tier
            elif pinned_strategy == "cookie_http" and crawl_session:
                cookies = await crawl_session.get_cookies_for_http()
                if cookies:
                    result = await _fetch_with_cookie_http(
                        url, request.timeout, cookies, proxy_url=proxy_url
                    )
                    html, sc, hdrs = result
                    if html and sc < 400 and not _looks_blocked(html):
                        raw_html, status_code, response_headers = html, sc, hdrs
                        fetched = True
                        winning_strategy = pinned_strategy
                        winning_tier = pinned_tier
            elif _is_stealth_pinned and settings.STEALTH_ENGINE_URL:
                use_ff = pinned_strategy == "stealth_firefox"
                result = await _fetch_via_stealth_engine(
                    url, request, use_firefox=use_ff, proxy=proxy_playwright
                )
                html = result[0]
                if html and not _looks_blocked(html):
                    raw_html, status_code, screenshot_b64, action_screenshots, response_headers = result
                    fetched = True
                    winning_strategy = pinned_strategy
                    winning_tier = pinned_tier
            if fetched:
                logger.debug(f"Pinned strategy hit for {url}: {pinned_strategy}")
        except Exception as e:
            logger.debug(f"Pinned strategy {pinned_strategy} failed for {url}: {e}")

    # === Tier 0: Strategy cache hit ===
    if not fetched and starting_tier == 0 and strategy_data and not needs_browser:
        last_strategy = strategy_data.get("last_success_strategy", "")
        tier_start = time.time()
        try:
            if last_strategy.startswith("curl_cffi:"):
                profile = last_strategy.split(":", 1)[1]
                result = await _fetch_with_curl_cffi_single(
                    url,
                    request.timeout,
                    profile=profile,
                    proxy_url=proxy_url,
                    custom_headers=_custom_h,
                    custom_cookies=_custom_c,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
            elif last_strategy == "httpx":
                result = await _fetch_with_httpx(
                    url,
                    request.timeout,
                    proxy_url=proxy_url,
                    custom_headers=_custom_h,
                    custom_cookies=_custom_c,
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = last_strategy
                    winning_tier = 0
            elif last_strategy == "cookie_http" and crawl_session:
                cookies = await crawl_session.get_cookies_for_http()
                if cookies:
                    result = await _fetch_with_cookie_http(
                        url, request.timeout, cookies, proxy_url=proxy_url
                    )
                    html, sc, hdrs = result
                    if html and sc < 400 and not _looks_blocked(html):
                        raw_html, status_code, response_headers = html, sc, hdrs
                        fetched = True
                        winning_strategy = last_strategy
                        winning_tier = 0
            if fetched:
                elapsed_ms = (time.time() - tier_start) * 1000
                await record_strategy_result(url, winning_strategy, 0, True, elapsed_ms)
        except Exception:
            pass

    # === Tier 0.5: Cookie HTTP ===
    if not fetched and crawl_session and not needs_browser:
        tier_start = time.time()
        try:
            cookies = await crawl_session.get_cookies_for_http()
            if cookies:
                result = await _fetch_with_cookie_http(
                    url, request.timeout, cookies, proxy_url=proxy_url
                )
                html, sc, hdrs = result
                if html and sc < 400 and not _looks_blocked(html):
                    raw_html, status_code, response_headers = html, sc, hdrs
                    fetched = True
                    winning_strategy = "cookie_http"
                    winning_tier = 0
                    elapsed_ms = (time.time() - tier_start) * 1000
                    await record_strategy_result(
                        url, "cookie_http", 0, True, elapsed_ms
                    )
        except Exception:
            pass

    # === Tier 1: HTTP parallel ===
    if not fetched and not needs_browser and starting_tier <= 1:
        tier_start = time.time()
        http_coros = [
            (
                "curl_cffi_multi",
                _fetch_with_curl_cffi_multi(
                    url,
                    request.timeout,
                    proxy_url=proxy_url,
                    custom_headers=_custom_h,
                    custom_cookies=_custom_c,
                ),
            ),
        ]
        if not hard_site:
            http_coros.append(
                (
                    "httpx",
                    _fetch_with_httpx(
                        url,
                        request.timeout,
                        proxy_url=proxy_url,
                        custom_headers=_custom_h,
                        custom_cookies=_custom_c,
                    ),
                )
            )

        race = await _race_strategies(http_coros, url, timeout=10)
        if race.best_html and len(race.best_html) > len(raw_html_best):
            raw_html_best = race.best_html
        if race.success:
            html, sc, hdrs = race.winner_result
            raw_html, status_code, response_headers = html, sc, hdrs
            fetched = True
            winning_strategy = (
                "curl_cffi:chrome124"
                if race.winner_name == "curl_cffi_multi"
                else race.winner_name
            )
            winning_tier = 1
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(url, winning_strategy, 1, True, elapsed_ms)

    # === Tier 2: Browser ===
    # For hard sites with starting_tier <= 2, combine Tier 2 + Tier 3 into one big race
    # When stealth-engine is available, race it alongside local fallbacks.
    _skip_tier3_fetch = False
    _has_stealth_engine_fetch = bool(settings.STEALTH_ENGINE_URL)
    if not fetched and starting_tier <= 2:
        tier_start = time.time()

        def _validate_browser(result):
            html = result[0] if isinstance(result, tuple) else result
            return bool(html) and not _looks_blocked(html)

        if crawl_session:
            browser_coros = [
                (
                    "chromium_stealth",
                    _fetch_with_browser_session(url, request, crawl_session),
                )
            ]
            # For hard sites, also race a fresh browser alongside the session
            if hard_site:
                browser_coros.append(
                    (
                        "chromium_stealth_fresh",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright),
                    ),
                )
                if _has_stealth_engine_fetch:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                    browser_coros.append((
                        "stealth_firefox",
                        _fetch_via_stealth_engine(url, request, use_firefox=True, proxy=proxy_playwright),
                    ))
                t2_timeout = 35
            else:
                if _has_stealth_engine_fetch:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                t2_timeout = 20
        else:
            if hard_site:
                browser_coros = [
                    (
                        "chromium_stealth",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, stealth=True),
                    ),
                    (
                        "firefox_stealth",
                        _fetch_with_browser_stealth(
                            url, request, proxy=proxy_playwright, use_firefox=True, stealth=True
                        ),
                    ),
                ]
                if _has_stealth_engine_fetch:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                    browser_coros.append((
                        "stealth_firefox",
                        _fetch_via_stealth_engine(url, request, use_firefox=True, proxy=proxy_playwright),
                    ))
                # Race Tier 2 AND Tier 3 concurrently for massive speed win
                if starting_tier <= 3:
                    heavy_coros = [
                        (
                            "google_search_chain",
                            _fetch_with_google_search_chain(
                                url, request, proxy=proxy_playwright
                            ),
                        ),
                        (
                            "advanced_prewarm",
                            _fetch_with_advanced_prewarm(
                                url, request, proxy=proxy_playwright
                            ),
                        ),
                    ]
                    browser_coros.extend(heavy_coros)
                    _skip_tier3_fetch = True
                    t2_timeout = 35
                else:
                    t2_timeout = 30
            else:
                # Non-hard sites: light mode — no stealth scripts, no warm-up
                browser_coros = []
                if _has_stealth_engine_fetch:
                    browser_coros.append((
                        "stealth_chromium",
                        _fetch_via_stealth_engine(url, request, use_firefox=False, proxy=proxy_playwright),
                    ))
                browser_coros.append(
                    (
                        "chromium_light",
                        _fetch_with_browser_stealth(url, request, proxy=proxy_playwright, stealth=False),
                    ),
                )
                browser_coros.append(
                    (
                        "firefox_light",
                        _fetch_with_browser_stealth(
                            url, request, proxy=proxy_playwright, use_firefox=True, stealth=False
                        ),
                    ),
                )
                t2_timeout = 20

        race = await _race_strategies(
            browser_coros, url, validate_fn=_validate_browser, timeout=t2_timeout
        )
        if race.best_html and len(race.best_html) > len(raw_html_best):
            raw_html_best = race.best_html
        if race.success:
            (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            ) = race.winner_result
            fetched = True
            winning_strategy = race.winner_name
            # Determine correct tier based on which strategy won
            if race.winner_name in ("google_search_chain", "advanced_prewarm"):
                winning_tier = 3
            else:
                winning_tier = 2
            elapsed_ms = (time.time() - tier_start) * 1000
            await record_strategy_result(
                url, winning_strategy, winning_tier, True, elapsed_ms
            )

    # === Tier 3: Heavy race (hard sites) ===
    if not fetched and hard_site and starting_tier <= 3 and not _skip_tier3_fetch:
        tier_start = time.time()
        heavy_coros = [
            (
                "google_search_chain",
                _fetch_with_google_search_chain(url, request, proxy=proxy_playwright),
            ),
            (
                "advanced_prewarm",
                _fetch_with_advanced_prewarm(url, request, proxy=proxy_playwright),
            ),
        ]

        def _validate_browser(result):
            html = result[0] if isinstance(result, tuple) else result
            return bool(html) and not _looks_blocked(html)

        race = await _race_strategies(
            heavy_coros, url, validate_fn=_validate_browser, timeout=35
        )
        if race.best_html and len(race.best_html) > len(raw_html_best):
            raw_html_best = race.best_html
        if race.success:
            (
                raw_html,
                status_code,
                screenshot_b64,
                action_screenshots,
                response_headers,
            ) = race.winner_result
            fetched = True
            winning_strategy = race.winner_name
            winning_tier = 3

    # === Tier 4: Fallback ===
    if not fetched:
        fallback_coros = [
            (
                "google_cache",
                _fetch_from_google_cache(url, request.timeout, proxy_url=proxy_url),
            ),
            (
                "wayback",
                _fetch_from_wayback_machine(url, request.timeout, proxy_url=proxy_url),
            ),
        ]

        def _validate_fallback(result):
            html = result[0] if isinstance(result, tuple) else result
            return bool(html) and len(html) > 500 and not _looks_blocked(html)

        race = await _race_strategies(
            fallback_coros, url, validate_fn=_validate_fallback, timeout=12
        )
        if race.best_html and len(race.best_html) > len(raw_html_best):
            raw_html_best = race.best_html
        if race.success:
            html, sc, hdrs = race.winner_result
            raw_html, status_code, response_headers = html, sc, hdrs
            fetched = True
            winning_strategy = race.winner_name
            winning_tier = 4

    # Use best available — but NOT if it's blocked content (e.g. Amazon bot page).
    # Returning None lets the crawl worker fall back to full scrape_url which has
    # more aggressive strategies.
    if not fetched and raw_html_best:
        if _looks_blocked(raw_html_best):
            logger.warning(
                f"Fetch-only {url}: best content looks blocked ({len(raw_html_best)} chars), returning None for fallback"
            )
            return None
        raw_html = raw_html_best
    if not raw_html:
        return None

    logger.info(
        f"Fetch-only {url} in {time.time() - start_time:.1f}s (tier={winning_tier}, strategy={winning_strategy})"
    )

    return {
        "raw_html": raw_html,
        "status_code": status_code,
        "response_headers": response_headers,
        "screenshot_b64": screenshot_b64,
        "action_screenshots": action_screenshots or [],
        "winning_strategy": winning_strategy,
        "winning_tier": winning_tier,
    }


def extract_content(
    raw_html: str,
    url: str,
    request: ScrapeRequest,
    status_code: int,
    response_headers: dict,
    screenshot_b64: str | None,
    action_screenshots: list[str] | None = None,
) -> ScrapeData:
    """CPU-bound content extraction — synchronous, designed for ThreadPoolExecutor."""
    result_data: dict[str, Any] = {}

    if "markdown" in request.formats:
        # Fast path: combined extraction + markdown in 1 parse (saves ~200-350ms)
        clean_html, result_data["markdown"] = extract_and_convert(
            raw_html,
            url,
            only_main_content=request.only_main_content,
            include_tags=request.include_tags,
            exclude_tags=request.exclude_tags,
        )
    else:
        clean_html = (
            extract_main_content(raw_html, url)
            if request.only_main_content
            else raw_html
        )
        if request.include_tags or request.exclude_tags:
            clean_html = apply_tag_filters(
                clean_html, request.include_tags, request.exclude_tags
            )
    if "links" in request.formats:
        result_data["links"] = extract_links(raw_html, url)
        result_data["links_detail"] = extract_links_detailed(raw_html, url)
    if "structured_data" in request.formats:
        result_data["structured_data"] = extract_structured_data(raw_html)
    if "headings" in request.formats:
        result_data["headings"] = extract_headings(raw_html)
    if "images" in request.formats:
        result_data["images"] = extract_images(raw_html, url)
    if "html" in request.formats:
        result_data["html"] = clean_html
    if "raw_html" in request.formats:
        result_data["raw_html"] = raw_html
    if "screenshot" in request.formats:
        if screenshot_b64:
            result_data["screenshot"] = screenshot_b64
        elif action_screenshots:
            result_data["screenshot"] = action_screenshots[-1]

    metadata_dict = extract_metadata(raw_html, url, status_code, response_headers or {})
    metadata = PageMetadata(**metadata_dict)

    return ScrapeData(
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
