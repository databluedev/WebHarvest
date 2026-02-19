import base64
import logging
import random
import re
import time
from typing import Any
from urllib.parse import quote_plus, urlparse

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
    "please click here if you are not redirected",
    "if you are not redirected within",
    "having trouble accessing google",
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
    r"fls-na\.amazon\.",
    r"unagi\.amazon\.",
    r".*\.akstat\.io",
    r".*\.akamaized\.net",
    r"px-captcha",
    r".*\.perimeterx\.",
    r"js\.datadome\.co",
    r"api\.datadome\.co",
    r"challenges\.cloudflare\.com",
    r"cdn-cgi/challenge-platform",
    r".*\.kasada\.io",
    r".*\.shape\.ag",
    r"fingerprintjs",
    r"recaptcha",
]

_BOT_DETECTION_REGEX: re.Pattern | None = None

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
        base["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    elif profile.startswith("edge"):
        base["Sec-Ch-Ua"] = '"Chromium";v="101", "Microsoft Edge";v="101", "Not A;Brand";v="99"'
        base["Sec-Ch-Ua-Mobile"] = "?0"
        base["Sec-Ch-Ua-Platform"] = '"Windows"'
    elif profile.startswith("chrome"):
        version = profile.replace("chrome", "")
        base["Sec-Ch-Ua"] = f'"Chromium";v="{version}", "Google Chrome";v="{version}", "Not-A.Brand";v="99"'
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
                await page.wait_for_timeout(random.randint(500, 1000))
                return
        except Exception:
            continue


def _looks_blocked(html: str) -> bool:
    if not html:
        return True

    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body_html = body_match.group(1) if body_match else html

    # Strip <script> and <style> tags AND their content before measuring text
    visible_html = re.sub(r"<script[^>]*>.*?</script>", " ", body_html, flags=re.DOTALL | re.IGNORECASE)
    visible_html = re.sub(r"<style[^>]*>.*?</style>", " ", visible_html, flags=re.DOTALL | re.IGNORECASE)
    visible_html = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", visible_html, flags=re.DOTALL | re.IGNORECASE)
    body_text = re.sub(r"<[^>]+>", " ", visible_html).strip().lower()
    # Collapse whitespace for accurate length measurement
    body_text = re.sub(r"\s+", " ", body_text)

    # Pages with substantial visible text content are never block pages
    if len(body_text) > 5000:
        return False

    if len(body_text) < 1500:
        for pattern in _BLOCK_PATTERNS:
            if pattern in body_text:
                return True

    # Only check head for patterns that STRONGLY indicate a block page
    # Avoid generic words like "captcha" / "robot" which appear in normal content
    head = html[:5000].lower()
    for pattern in ["javascript is disabled", "enable javascript",
                    "attention required", "just a moment", "checking your browser",
                    "please wait while we verify", "verify you are human",
                    "are you a robot", "not a robot",
                    "please click here if you are not redirected",
                    "having trouble accessing google"]:
        if pattern in head:
            return True

    if len(body_text) < 300 and ("<noscript" in html.lower()):
        return True

    # Google redirect/interstitial page (from Google Cache attempts)
    if len(body_text) < 500:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match and "google" in title_match.group(1).lower():
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
# Cache/archive content strippers
# ---------------------------------------------------------------------------

def _strip_google_cache_banner(html: str) -> str:
    """Remove Google's cache header/banner from cached HTML."""
    html = re.sub(
        r'<div[^>]*(?:id|class)=["\']google-cache-hdr["\'][^>]*>.*?</div>\s*(?:</div>)*',
        "", html, count=1, flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r'<div[^>]*style=["\'][^"\']*text-align:\s*center[^"\']*["\'][^>]*>.*?This is Google\'s cache.*?</div>',
        "", html, count=1, flags=re.DOTALL | re.IGNORECASE,
    )
    return html


def _strip_wayback_toolbar(html: str) -> str:
    """Remove Wayback Machine injected toolbar and scripts."""
    html = re.sub(
        r'<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->',
        "", html, flags=re.DOTALL,
    )
    html = re.sub(
        r'<script[^>]*(?:wombat|archive\.org)[^>]*>.*?</script>',
        "", html, flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r'<(?:link|style)[^>]*(?:archive\.org|wayback)[^>]*(?:/>|>.*?</(?:link|style)>)',
        "", html, flags=re.DOTALL | re.IGNORECASE,
    )
    return html


# ---------------------------------------------------------------------------
# Main scrape
# ---------------------------------------------------------------------------

async def scrape_url(
    request: ScrapeRequest,
    proxy_manager=None,
) -> ScrapeData:
    """
    Scrape a URL with maximum anti-detection — 8-strategy cascade.

    Pipeline:
    1. curl_cffi multi-profile (5 TLS fingerprints)
    2. httpx HTTP/2 with 10+ header rotation (non-hard sites)
    3. Chromium stealth + request interception
    4. Firefox stealth + request interception
    5. Google Search referrer chain (hard sites only)
    6. Advanced session pre-warming (hard sites only)
    7. Google Cache fallback
    8. Wayback Machine fallback (last resort)
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

    # === Strategy 1: curl_cffi multi-profile (ALL sites) ===
    if not needs_browser:
        try:
            raw_html, status_code, response_headers = await _fetch_with_curl_cffi_multi(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and status_code < 400 and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"curl_cffi multi succeeded for {url}")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
                logger.info(f"curl_cffi multi blocked/failed for {url} (status={status_code}, best={len(raw_html_best)}), escalating")
        except Exception as e:
            logger.warning(f"curl_cffi multi exception for {url}: {e}")

    # === Strategy 2: httpx HTTP/2 with header rotation (non-hard sites) ===
    if not fetched and not needs_browser and not hard_site:
        try:
            raw_html, status_code, response_headers = await _fetch_with_httpx(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and status_code < 400 and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"httpx succeeded for {url}")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"httpx exception for {url}: {e}")

    # === Strategy 3: Chromium stealth + request interception ===
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

    # === Strategy 4: Firefox stealth + request interception ===
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

    # === Strategy 5: Google Search referrer chain (hard sites only) ===
    if not fetched and hard_site:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_google_search_chain(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Google Search chain succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Google Search chain exception for {url}: {e}")

    # === Strategy 6: Advanced session pre-warming (hard sites only) ===
    if not fetched and hard_site:
        try:
            raw_html, status_code, screenshot_b64, action_screenshots, response_headers = (
                await _fetch_with_advanced_prewarm(url, request, proxy=proxy_playwright)
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Advanced prewarm succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Advanced prewarm exception for {url}: {e}")

    # === Strategy 7: Google Cache fallback (all sites) ===
    if not fetched:
        try:
            raw_html, status_code, response_headers = await _fetch_from_google_cache(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and not _looks_blocked(raw_html):
                fetched = True
                logger.info(f"Google Cache succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Google Cache exception for {url}: {e}")

    # === Strategy 8: Wayback Machine fallback (all sites, last resort) ===
    if not fetched:
        try:
            raw_html, status_code, response_headers = await _fetch_from_wayback_machine(
                url, request.timeout, proxy_url=proxy_url
            )
            if raw_html and len(raw_html) > 500:
                fetched = True
                logger.info(f"Wayback Machine succeeded for {url} ({len(raw_html)} chars)")
            else:
                if raw_html and len(raw_html) > len(raw_html_best):
                    raw_html_best = raw_html
                raw_html = ""
        except Exception as e:
            logger.warning(f"Wayback Machine exception for {url}: {e}")

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
# Strategy 1: curl_cffi — multi-profile TLS fingerprint impersonation
# ---------------------------------------------------------------------------

async def _fetch_with_curl_cffi_multi(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    """HTTP fetch trying 5 TLS fingerprints in sequence. Early exit on success."""
    from curl_cffi.requests import AsyncSession

    timeout_seconds = timeout / 1000
    best_html = ""
    best_status = 0
    best_headers: dict[str, str] = {}

    for profile in _CURL_CFFI_PROFILES:
        try:
            headers = _get_headers_for_profile(profile, url)
            async with AsyncSession(impersonate=profile) as session:
                kwargs: dict[str, Any] = dict(
                    timeout=timeout_seconds,
                    allow_redirects=True,
                    headers=headers,
                )
                if proxy_url:
                    kwargs["proxy"] = proxy_url

                response = await session.get(url, **kwargs)
                resp_headers = {k.lower(): v for k, v in response.headers.items()}
                html = response.text

                if html and response.status_code < 400 and not _looks_blocked(html):
                    logger.info(f"curl_cffi profile {profile} succeeded for {url} ({len(html)} chars)")
                    return html, response.status_code, resp_headers

                # Track best result for fallback
                if html and len(html) > len(best_html):
                    best_html = html
                    best_status = response.status_code
                    best_headers = resp_headers

                logger.debug(f"curl_cffi profile {profile} blocked/failed for {url} (status={response.status_code})")
        except Exception as e:
            logger.debug(f"curl_cffi profile {profile} exception for {url}: {e}")
            continue

    return best_html, best_status, best_headers


# ---------------------------------------------------------------------------
# Strategy 2: httpx with HTTP/2 + header rotation
# ---------------------------------------------------------------------------

async def _fetch_with_httpx(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    timeout_seconds = timeout / 1000
    headers = random.choice(_HEADER_ROTATION_POOL).copy()
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
# Strategy 3/4: Browser with stealth + request interception + warm-up
# ---------------------------------------------------------------------------

async def _fetch_with_browser_stealth(
    url: str,
    request: ScrapeRequest,
    proxy: dict | None = None,
    use_firefox: bool = False,
) -> tuple[str, int, str | None, list[str], dict[str, str]]:
    """Fast browser fetch: domcontentloaded + short networkidle + request interception."""
    screenshot_b64 = None
    action_screenshots = []
    status_code = 0
    response_headers: dict[str, str] = {}

    async with browser_pool.get_page(proxy=proxy, use_firefox=use_firefox, target_url=url) as page:
        # Set up request interception (blocks bot detection scripts on hard sites)
        await _setup_request_interception(page, url)

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
            await page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            # Google blocked too — fall back to direct navigation
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
            raw_html = await page.content()
            return raw_html, status_code, screenshot_b64, action_screenshots, response_headers

        await page.wait_for_timeout(random.randint(1000, 2000))

        # 2. Accept Google consent (GDPR)
        await _try_accept_google_consent(page)

        # 3. Type search query character-by-character with human-like delays
        search_input = await page.query_selector("textarea[name='q'], input[name='q']")
        if not search_input:
            # Fallback: direct navigation
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
            raw_html = await page.content()
            return raw_html, status_code, screenshot_b64, action_screenshots, response_headers

        await search_input.click()
        for char in query:
            await search_input.type(char, delay=random.randint(50, 150))
            if random.random() < 0.1:  # Occasional pause
                await page.wait_for_timeout(random.randint(200, 500))

        await page.wait_for_timeout(random.randint(300, 700))
        await page.keyboard.press("Enter")

        # 4. Wait for results
        try:
            await page.wait_for_selector("#search", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(random.randint(1000, 2000))

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
                        await page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
                        await page.wait_for_timeout(random.randint(100, 300))

                    await link.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # Direct navigation as fallback
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        else:
            # Wait for navigation after click
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

        await page.wait_for_timeout(random.randint(1500, 3000))
        await _try_accept_cookies(page)

        # 6. If landed on domain but not exact page, navigate internally
        current_url = page.url
        if domain in current_url and current_url != url:
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                status_code = response.status if response else 0
                if response:
                    response_headers = {k.lower(): v for k, v in response.headers.items()}
                await page.wait_for_timeout(random.randint(1000, 2000))
            except Exception:
                pass

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        await _try_accept_cookies(page)

        if request.wait_for > 0:
            await page.wait_for_timeout(request.wait_for)

        if request.actions:
            actions_dicts = [a.model_dump() for a in request.actions]
            action_screenshots = await browser_pool.execute_actions(page, actions_dicts)

        if "screenshot" in request.formats:
            screenshot_bytes = await page.screenshot(type="png", full_page=True)
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
            "in": "india", "uk": "uk", "de": "germany", "fr": "france",
            "jp": "japan", "ca": "canada", "au": "australia", "es": "spain", "it": "italy",
        }
        country = country_map.get(tld_parts[-1], tld_parts[-1])
        search_term = f"{site_name} {country}"
    else:
        search_term = site_name

    async with browser_pool.get_page(proxy=proxy, target_url=url) as page:
        await _setup_request_interception(page, url)

        # --- Phase 1: Google session ---
        try:
            await page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(random.randint(1000, 2000))

            await _try_accept_google_consent(page)

            # Brief mouse interaction on Google (builds cookies)
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            for _ in range(2):
                await page.mouse.move(
                    random.randint(200, vp["width"] - 200),
                    random.randint(100, vp["height"] - 200),
                    steps=random.randint(8, 15),
                )
                await page.wait_for_timeout(random.randint(200, 500))
        except Exception:
            pass

        # --- Phase 2: Search & click-through ---
        try:
            search_input = await page.query_selector("textarea[name='q'], input[name='q']")
            if search_input:
                await search_input.click()
                for char in search_term:
                    await search_input.type(char, delay=random.randint(50, 150))
                    if random.random() < 0.1:
                        await page.wait_for_timeout(random.randint(200, 400))

                await page.wait_for_timeout(random.randint(300, 600))
                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_selector("#search", timeout=8000)
                except Exception:
                    pass
                await page.wait_for_timeout(random.randint(1000, 2000))

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
                                    box["x"] + box["width"] / 2 + random.randint(-10, 10),
                                    box["y"] + box["height"] / 2 + random.randint(-3, 3),
                                    steps=random.randint(10, 20),
                                )
                            await link.click()
                            try:
                                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            break
                    except Exception:
                        continue
        except Exception:
            pass

        await page.wait_for_timeout(random.randint(1500, 3000))
        await _try_accept_cookies(page)

        # --- Phase 3: Browse naturally (2-3 internal pages) ---
        current = page.url
        if domain in current:
            try:
                vp = page.viewport_size or {"width": 1920, "height": 1080}
                for _ in range(random.randint(2, 3)):
                    # Mouse movements
                    for _ in range(random.randint(2, 3)):
                        await page.mouse.move(
                            random.randint(100, vp["width"] - 100),
                            random.randint(100, vp["height"] - 100),
                            steps=random.randint(8, 15),
                        )
                        await page.wait_for_timeout(random.randint(200, 400))

                    # Scroll
                    await page.mouse.wheel(0, random.randint(200, 500))
                    await page.wait_for_timeout(random.randint(500, 1000))

                    # Click a random internal link
                    internal_links = await page.query_selector_all(f"a[href*='{domain}']")
                    if internal_links:
                        link = random.choice(internal_links[:10])
                        try:
                            await link.scroll_into_view_if_needed()
                            await page.wait_for_timeout(random.randint(200, 400))
                            await link.click()
                            await page.wait_for_load_state("domcontentloaded", timeout=8000)
                        except Exception:
                            pass

                    await page.wait_for_timeout(random.randint(1000, 2000))
                    await _try_accept_cookies(page)
            except Exception:
                pass

        # --- Phase 4: Navigate to actual target URL ---
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status_code = response.status if response else 0
            if response:
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Final human interaction
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        for _ in range(random.randint(3, 5)):
            await page.mouse.move(
                random.randint(100, vp["width"] - 100),
                random.randint(100, vp["height"] - 100),
                steps=random.randint(8, 15),
            )
            await page.wait_for_timeout(random.randint(200, 500))

        await _try_accept_cookies(page)

        # Challenge re-check loop
        for _ in range(2):
            html_check = await page.content()
            if not _looks_blocked(html_check):
                break
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


# ---------------------------------------------------------------------------
# Strategy 7: Google Cache fallback
# ---------------------------------------------------------------------------

async def _fetch_from_google_cache(
    url: str, timeout: int, proxy_url: str | None = None
) -> tuple[str, int, dict[str, str]]:
    """Fetch content from Google's cache — bypasses all site-level protection."""
    from curl_cffi.requests import AsyncSession

    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}"
    timeout_seconds = timeout / 1000

    async with AsyncSession(impersonate="chrome124") as session:
        kwargs: dict[str, Any] = dict(
            timeout=timeout_seconds,
            allow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Referer": "https://www.google.com/",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        if proxy_url:
            kwargs["proxy"] = proxy_url

        response = await session.get(cache_url, **kwargs)
        html = response.text

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

    client_kwargs: dict[str, Any] = dict(
        follow_redirects=True, timeout=timeout_seconds,
    )
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    async with httpx.AsyncClient(**client_kwargs) as client:
        # 1. Check availability
        api_url = f"https://archive.org/wayback/available?url={quote_plus(url)}&timestamp=20260219"
        resp = await client.get(api_url)
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
