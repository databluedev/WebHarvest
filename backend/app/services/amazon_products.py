"""Amazon Products scraper — HTTP-only with DOM parsing.

Strategy chain (per page, with retry):
1. curl_cffi with Chrome TLS impersonation (works from residential IPs)
2. httpx fallback
3. Proxy variants of curl_cffi / httpx (if BUILTIN_PROXY_URL configured)
4. Stealth engine (Patchright — if STEALTH_ENGINE_URL configured)
5. nodriver (real browser via NoDriverPool)

Product data is parsed from the search results DOM using BeautifulSoup.
Amazon returns ~48 products per page, max 20 pages (~960 products).

Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import logging
import random
import re
import time
from urllib.parse import quote_plus

import httpx

from app.schemas.data_amazon import AmazonProduct, AmazonProductsResponse

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes

_SORT_MAP = {
    "price_low": "price-asc-rank",
    "price_high": "price-desc-rank",
    "rating": "review-rank",
    "newest": "date-desc-rank",
}

_AMAZON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


# ═══════════════════════════════════════════════════════════════════
#  Cache
# ═══════════════════════════════════════════════════════════════════


def _cache_key(
    query: str,
    domain: str,
    page: int,
    num_results: int,
    sort_by: str | None,
    min_price: int | None,
    max_price: int | None,
    prime_only: bool,
) -> str:
    raw = (
        f"amazon:{query}|{domain}|{page}|{num_results}"
        f"|{sort_by or ''}|{min_price or ''}|{max_price or ''}"
        f"|{prime_only}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:amazon:{h}"


# ═══════════════════════════════════════════════════════════════════
#  URL builder
# ═══════════════════════════════════════════════════════════════════


def _build_url(
    query: str,
    domain: str,
    page: int = 1,
    sort_by: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    prime_only: bool = False,
) -> str:
    """Build an Amazon search URL with filters."""
    encoded_query = quote_plus(query)
    url = f"https://www.{domain}/s?k={encoded_query}&page={page}&ref=sr_pg_{page}"

    if sort_by and sort_by in _SORT_MAP:
        url += f"&s={_SORT_MAP[sort_by]}"

    # Price range filter — Amazon uses paise/cents (multiply by 100)
    if min_price is not None or max_price is not None:
        low = (min_price or 0) * 100
        high = (max_price * 100) if max_price is not None else ""
        url += f"&rh=p_36%3A{low}-{high}"

    if prime_only:
        url += "&rh=p_85%3A10440599031"

    return url


# ═══════════════════════════════════════════════════════════════════
#  HTTP fetchers
# ═══════════════════════════════════════════════════════════════════


def _is_valid_search_page(html: str) -> bool:
    """Check that the response is a valid search page, not a CAPTCHA."""
    if not html:
        return False
    # CAPTCHA / bot detection pages
    captcha_markers = [
        "Type the characters you see in this image",
        "Sorry, we just need to make sure you're not a robot",
        "api-services-support@amazon",
        "Enter the characters you see below",
    ]
    for marker in captcha_markers:
        if marker in html:
            logger.warning("Amazon returned CAPTCHA page")
            return False
    # Must have search results container
    if 's-search-results' not in html and 's-result-item' not in html:
        return False
    return True


async def _get_proxy_url() -> str | None:
    """Get a proxy URL from the builtin proxy pool."""
    try:
        from app.services.proxy import get_builtin_proxy_manager, ProxyManager

        pm = await get_builtin_proxy_manager()
        if pm and pm.has_proxies:
            proxy = await pm.get_random_weighted()
            if proxy:
                return ProxyManager.to_httpx(proxy)
    except Exception as e:
        logger.debug("Could not get proxy: %s", e)
    return None


async def _fetch_via_curl_cffi(url: str, domain: str, proxy_url: str | None = None) -> str | None:
    """Fetch with curl_cffi — required for Amazon's TLS fingerprinting."""
    try:
        from curl_cffi.requests import AsyncSession

        headers = {**_AMAZON_HEADERS}
        headers["Referer"] = f"https://www.{domain}/"

        async with AsyncSession(impersonate="chrome124") as session:
            kwargs: dict = {
                "headers": headers,
                "timeout": 20,
                "allow_redirects": True,
            }
            if proxy_url:
                kwargs["proxy"] = proxy_url

            resp = await session.get(url, **kwargs)
            if resp.status_code == 200 and _is_valid_search_page(resp.text):
                return resp.text
            logger.warning(
                "Amazon curl_cffi returned %d%s",
                resp.status_code,
                " (via proxy)" if proxy_url else "",
            )
    except Exception as e:
        logger.warning("curl_cffi Amazon fetch failed: %s", e)
    return None


async def _fetch_via_httpx(url: str, domain: str, proxy_url: str | None = None) -> str | None:
    """Fetch with httpx — fallback."""
    try:
        headers = {**_AMAZON_HEADERS}
        headers["Referer"] = f"https://www.{domain}/"

        kwargs: dict = {
            "timeout": 20,
            "follow_redirects": True,
            "headers": headers,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and _is_valid_search_page(resp.text):
                return resp.text
            logger.warning(
                "Amazon httpx returned %d%s",
                resp.status_code,
                " (via proxy)" if proxy_url else "",
            )
    except Exception as e:
        logger.warning("httpx Amazon fetch failed: %s", e)
    return None


async def _fetch_via_stealth_engine(url: str, domain: str) -> str | None:
    """Fetch via stealth engine sidecar (Patchright + fingerprint spoofing)."""
    try:
        from app.config import settings as app_settings

        stealth_url = app_settings.STEALTH_ENGINE_URL
        if not stealth_url:
            return None

        payload = {
            "url": url,
            "timeout": 25000,
            "wait_after_load": 3000,
            "use_firefox": False,
            "screenshot": False,
            "mobile": False,
            "headers": {
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": f"https://www.{domain}/",
            },
        }

        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post(f"{stealth_url}/scrape", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                html = data.get("html", "")
                if html and _is_valid_search_page(html):
                    logger.info("Stealth engine succeeded for Amazon")
                    return html
                logger.warning("Stealth engine: invalid page (CAPTCHA or empty)")
            else:
                logger.warning("Stealth engine returned %d", resp.status_code)
    except Exception as e:
        logger.warning("Stealth engine Amazon fetch failed: %s", e)
    return None


async def _fetch_via_nodriver(url: str, wait_time: float = 5) -> str | None:
    """Fetch with nodriver — real browser, bypasses bot detection."""
    try:
        from app.services.nodriver_helper import fetch_page_nodriver

        result = await fetch_page_nodriver(
            url,
            wait_selector='div[data-component-type="s-search-result"]',
            wait_selector_fallback=".s-search-results",
            wait_time=wait_time,
        )
        html = result[0] if isinstance(result, tuple) else result
        if html and _is_valid_search_page(html):
            return html
        logger.warning(
            "nodriver fetch: %d chars, valid=%s",
            len(html) if html else 0,
            bool(html and _is_valid_search_page(html)) if html else False,
        )
    except Exception as e:
        logger.warning("nodriver Amazon fetch failed: %s", e)
    return None


async def _fetch_html(url: str, domain: str) -> str | None:
    """Try fetch strategies with fallback chain.

    Order: direct HTTP → proxy HTTP → stealth engine → nodriver (with retry).
    """
    # 1. Direct (no proxy) — works from residential IPs
    html = await _fetch_via_curl_cffi(url, domain)
    if html:
        return html

    html = await _fetch_via_httpx(url, domain)
    if html:
        return html

    # 2. Retry with proxy if available (Amazon blocks datacenter IPs)
    proxy_url = await _get_proxy_url()
    if proxy_url:
        logger.info("Retrying Amazon fetch with proxy")
        html = await _fetch_via_curl_cffi(url, domain, proxy_url=proxy_url)
        if html:
            return html

        html = await _fetch_via_httpx(url, domain, proxy_url=proxy_url)
        if html:
            return html

    # 3. Stealth engine (Patchright with full fingerprint spoofing)
    html = await _fetch_via_stealth_engine(url, domain)
    if html:
        return html

    # 4. nodriver (real browser) — try twice with different wait times
    html = await _fetch_via_nodriver(url, wait_time=5)
    if html:
        return html

    # Retry nodriver with longer wait (Amazon sometimes loads late)
    await asyncio.sleep(random.uniform(1, 3))
    html = await _fetch_via_nodriver(url, wait_time=8)
    if html:
        return html

    return None


# ═══════════════════════════════════════════════════════════════════
#  DOM parser — BeautifulSoup
# ═══════════════════════════════════════════════════════════════════


def _parse_price(text: str | None) -> tuple[str | None, float | None, str | None]:
    """Parse a price string like '₹1,299.00' or '$29.99'.

    Returns (display_price, numeric_value, currency_symbol).
    """
    if not text:
        return None, None, None
    text = text.strip()
    if not text:
        return None, None, None

    # Extract currency symbol (first non-digit, non-space, non-comma, non-dot char)
    currency = None
    for ch in text:
        if not ch.isdigit() and ch not in " ,.\n\t":
            currency = ch
            break

    # Extract numeric value
    numeric_str = re.sub(r"[^\d.]", "", text)
    try:
        value = float(numeric_str) if numeric_str else None
    except ValueError:
        value = None

    return text, value, currency


def _parse_products(html: str, domain: str, start_position: int = 1) -> list[AmazonProduct]:
    """Parse product cards from Amazon search results HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    products: list[AmazonProduct] = []
    position = start_position

    # Product cards: div with data-component-type="s-search-result" and data-asin
    cards = soup.select('div[data-component-type="s-search-result"][data-asin]')
    if not cards:
        # Fallback selector
        cards = soup.select("div[data-asin]")

    for card in cards:
        asin = card.get("data-asin", "").strip()
        if not asin:
            continue

        # Title
        title_el = card.select_one("h2 a span") or card.select_one("h2 span")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        # Product URL
        link_el = card.select_one("h2 a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            url = f"https://www.{domain}{href}"
        elif href:
            url = href
        else:
            url = f"https://www.{domain}/dp/{asin}"

        # Image
        img_el = card.select_one("img.s-image")
        image_url = img_el.get("src") if img_el else None

        # Price — current price (not strikethrough)
        price_el = card.select_one("span.a-price:not(.a-text-price) span.a-offscreen")
        price_display, price_value, currency = _parse_price(
            price_el.get_text(strip=True) if price_el else None
        )

        # Original price (strikethrough)
        orig_price_el = card.select_one("span.a-price.a-text-price span.a-offscreen")
        original_price = orig_price_el.get_text(strip=True) if orig_price_el else None

        # Discount — search for "% off" text in spans near price
        discount = None
        discount_el = card.select_one("span.savingsPercentage")
        if not discount_el:
            discount_el = card.select_one("span.s-savings-badge span")
        if not discount_el:
            for span in card.select("span"):
                span_text = span.get_text(strip=True)
                if re.search(r"\d+%\s*off", span_text, re.IGNORECASE) and len(span_text) < 30:
                    discount_el = span
                    break
        if discount_el:
            discount = discount_el.get_text(strip=True)

        # Rating
        rating = None
        rating_el = card.select_one("span.a-icon-alt")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            rating_match = re.search(r"(\d+\.?\d*)\s+out\s+of\s+5", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))

        # Review count — try aria-label first (e.g. "87,534 ratings"), then text
        review_count = None
        review_el = card.select_one('a[aria-label*="rating"]')
        if review_el:
            review_text = review_el.get("aria-label", "").replace(",", "").replace(".", "")
            review_match = re.search(r"([\d]+)\s*rating", review_text)
            if review_match:
                review_count = int(review_match.group(1))
        if review_count is None:
            review_el = card.select_one('a[href*="#customerReviews"] span')
            if review_el:
                review_text = review_el.get_text(strip=True).replace(",", "").replace(".", "")
                review_match = re.search(r"(\d+)", review_text)
                if review_match:
                    review_count = int(review_match.group(1))

        # Prime badge — check multiple selectors
        is_prime = bool(
            card.select_one("i.a-icon-prime")
            or card.select_one("span.a-icon-prime")
            or card.select_one("[aria-label='Amazon Prime']")
            or card.select_one("span.aok-relative.s-icon-text-medium")
        )

        # Sponsored
        is_sponsored = False
        sponsored_els = card.select("span.puis-label-popover-default span")
        for el in sponsored_els:
            if "Sponsored" in el.get_text(strip=True):
                is_sponsored = True
                break
        if not is_sponsored:
            # Alternative sponsored marker
            ad_label = card.select_one('span[data-component-type="s-ad-feedback"]')
            if ad_label:
                is_sponsored = True

        # Badge (Best Seller, Amazon's Choice, etc.)
        badge = None
        badge_el = card.select_one("span.a-badge-text") or card.select_one(
            'span[data-component-type="s-status-badge-component"] span.a-text-bold'
        )
        if badge_el:
            badge = badge_el.get_text(strip=True)

        # Delivery info
        delivery = None
        delivery_el = card.select_one('div[data-cy="delivery-recipe"]')
        if delivery_el:
            delivery = " ".join(delivery_el.get_text(separator=" ", strip=True).split())
        if not delivery:
            delivery_el = card.select_one("span.a-text-bold[aria-label]")
            if delivery_el:
                delivery = delivery_el.get("aria-label", "").strip() or delivery_el.get_text(strip=True)

        # Seller / brand
        seller = None
        seller_el = card.select_one("span.a-size-base-plus.a-color-base")
        if seller_el:
            seller = seller_el.get_text(strip=True)

        # Coupon
        coupon = None
        coupon_el = card.select_one('span[data-component-type="s-coupon-component"] span.a-color-base')
        if coupon_el:
            coupon = coupon_el.get_text(strip=True)
        if not coupon:
            coupon_el = card.select_one("span.s-coupon-unclipped span")
            if coupon_el:
                coupon = coupon_el.get_text(strip=True)

        products.append(
            AmazonProduct(
                position=position,
                asin=asin,
                title=title,
                url=url,
                image_url=image_url,
                price=price_display,
                price_value=price_value,
                currency=currency,
                original_price=original_price,
                discount=discount,
                rating=rating,
                review_count=review_count,
                is_prime=is_prime,
                is_sponsored=is_sponsored,
                badge=badge,
                delivery=delivery,
                seller=seller,
                coupon=coupon,
            )
        )
        position += 1

    return products


def _parse_total_results(html: str) -> str | None:
    """Extract total results text like '1-48 of over 10,000 results'."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    result_info = soup.select_one("span[data-component-type='s-result-info-bar'] span")
    if result_info:
        return result_info.get_text(strip=True)
    # Fallback
    result_info = soup.select_one("div.s-breadcrumb span.a-color-state")
    if result_info:
        return result_info.get_text(strip=True)
    return None


# ═══════════════════════════════════════════════════════════════════
#  Main service function
# ═══════════════════════════════════════════════════════════════════


async def amazon_products(
    query: str,
    num_results: int = 0,
    page: int = 1,
    domain: str = "amazon.in",
    sort_by: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    prime_only: bool = False,
    language: str = "en",
) -> AmazonProductsResponse:
    """Search Amazon and return structured product data."""
    query = query.strip()
    if not query:
        return AmazonProductsResponse(
            success=False,
            query=query,
            domain=domain,
            time_taken=0,
            error="Query cannot be empty.",
        )

    # Cache check
    key = _cache_key(query, domain, page, num_results, sort_by, min_price, max_price, prime_only)
    try:
        from app.core.cache import get_cached_response

        cached = await get_cached_response(key)
        if cached:
            logger.info("Amazon products cache hit: %s", query)
            return AmazonProductsResponse(**cached)
    except Exception:
        pass

    start = time.time()

    # Determine pagination strategy
    # 0 = fetch all pages; otherwise fetch enough pages to get num_results
    max_pages = 20
    if num_results > 0:
        # ~48 products per page
        max_pages = min(20, (num_results // 48) + 1)

    all_products: list[AmazonProduct] = []
    seen_asins: set[str] = set()
    pages_fetched = 0
    total_results_text: str | None = None
    first_url: str | None = None
    consecutive_fetch_fails = 0  # Fetch completely failed (503/CAPTCHA)
    consecutive_empty_results = 0  # Fetch succeeded but 0 new products

    current_page = page
    while current_page <= 20 and pages_fetched < max_pages:
        url = _build_url(
            query=query,
            domain=domain,
            page=current_page,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            prime_only=prime_only,
        )
        if first_url is None:
            first_url = url

        html = await _fetch_html(url, domain)
        if not html:
            consecutive_fetch_fails += 1
            logger.warning(
                "Amazon page %d fetch failed (%d consecutive)",
                current_page,
                consecutive_fetch_fails,
            )
            # Be more lenient with fetch failures — Amazon bot detection is
            # transient, so keep trying for a few more pages before giving up
            if consecutive_fetch_fails >= 3:
                logger.info("Stopping: %d consecutive fetch failures", consecutive_fetch_fails)
                break
            current_page += 1
            # Longer delay after failure to let bot detection cool down
            await asyncio.sleep(random.uniform(3, 6))
            continue

        consecutive_fetch_fails = 0
        pages_fetched += 1

        # Parse total results from first page
        if total_results_text is None:
            total_results_text = _parse_total_results(html)

        # Parse products
        page_products = _parse_products(
            html, domain, start_position=len(all_products) + 1
        )

        # Deduplicate by ASIN
        new_count = 0
        for product in page_products:
            if product.asin not in seen_asins:
                seen_asins.add(product.asin)
                all_products.append(product)
                new_count += 1

        if new_count == 0:
            consecutive_empty_results += 1
            if consecutive_empty_results >= 2:
                logger.info("Stopping: %d consecutive pages with no new products", consecutive_empty_results)
                break
        else:
            consecutive_empty_results = 0

        # Check if we have enough results
        if num_results > 0 and len(all_products) >= num_results:
            all_products = all_products[:num_results]
            break

        current_page += 1

        # Randomized delay between pages to avoid bot detection
        if current_page <= 20 and pages_fetched < max_pages:
            await asyncio.sleep(random.uniform(2, 4.5))

    # Re-number positions sequentially
    for i, product in enumerate(all_products):
        product.position = i + 1

    elapsed = time.time() - start

    result = AmazonProductsResponse(
        success=bool(all_products),
        query=query,
        domain=domain,
        total_results=total_results_text,
        pages_fetched=pages_fetched,
        time_taken=round(elapsed, 3),
        products=all_products,
        search_url=first_url,
    )

    # Cache result
    try:
        from app.core.cache import set_cached_response

        await set_cached_response(key, result.model_dump(), _CACHE_TTL)
    except Exception:
        pass

    return result
