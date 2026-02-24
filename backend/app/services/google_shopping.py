"""Google Shopping scraper — fetches and parses Google Shopping results.

Google Shopping is fully JavaScript-rendered. curl_cffi gets blocked by
Google's bot detection (returns a challenge page, not product data).

Strategy chain (per page):
1. Lightweight standalone Playwright — launch Chromium, render, extract, close
2. SearXNG shopping category (fallback, no filters)

Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.schemas.data_google import (
    GoogleShoppingProduct,
    GoogleShoppingResponse,
    RelatedSearch,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_RESULTS_PER_PAGE = 20
_MAX_PAGES = 5
_PAGE_DELAY = 2.0

# Currency symbol → code mapping
_CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "₩": "KRW",
    "R$": "BRL",
    "A$": "AUD",
    "C$": "CAD",
    "₺": "TRY",
    "zł": "PLN",
    "kr": "SEK",
    "Fr": "CHF",
}


# ═══════════════════════════════════════════════════════════════════
# Cache key
# ═══════════════════════════════════════════════════════════════════


def _cache_key(
    query: str,
    num: int,
    page: int,
    lang: str,
    country: str | None,
    sort_by: str | None,
    min_rating: int | None,
) -> str:
    raw = (
        f"shop|{query}|{num}|{page}|{lang}|{country or ''}"
        f"|{sort_by or ''}|{min_rating or ''}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:shopping:{h}"


# ═══════════════════════════════════════════════════════════════════
# URL builder
# ═══════════════════════════════════════════════════════════════════


def _build_shopping_url(
    query: str,
    num: int = 20,
    page: int = 1,
    lang: str = "en",
    country: str | None = None,
    sort_by: str | None = None,
    min_rating: int | None = None,
) -> str:
    """Build a Google Shopping URL with filter parameters."""
    params = [
        f"q={quote_plus(query)}",
        "tbm=shop",
        f"num={num}",
        f"hl={lang}",
    ]
    if page > 1:
        params.append(f"start={(page - 1) * num}")
    if country:
        params.append(f"gl={country}")

    # Build tbs filter string
    tbs_parts: list[str] = []

    sort_map = {
        "price_low": "p_ord:p",
        "price_high": "p_ord:pd",
        "rating": "p_ord:r",
        "reviews": "p_ord:rv",
    }
    if sort_by and sort_by in sort_map:
        tbs_parts.append(sort_map[sort_by])

    if min_rating and 1 <= min_rating <= 4:
        tbs_parts.append("mr:1")
        tbs_parts.append(f"avg_rating:{min_rating}00")

    if tbs_parts:
        seen: set[str] = set()
        deduped: list[str] = []
        for p in tbs_parts:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        params.append(f"tbs={','.join(deduped)}")

    return f"https://www.google.com/search?{'&'.join(params)}"


# ═══════════════════════════════════════════════════════════════════
# Price parser
# ═══════════════════════════════════════════════════════════════════


def _parse_price_string(text: str) -> tuple[float | None, str | None]:
    """Extract numeric price and currency code from a price string."""
    if not text:
        return None, None

    text = text.strip()

    currency = None
    for symbol, code in _CURRENCY_MAP.items():
        if symbol in text:
            currency = code
            break

    # Standard format: 1,299.99
    match = re.search(r"[\d,]+\.?\d*", text.replace(" ", ""))
    if match:
        num_str = match.group().replace(",", "")
        try:
            return float(num_str), currency
        except ValueError:
            pass

    # European format: 1.299,99
    match = re.search(r"[\d.]+,\d{2}", text.replace(" ", ""))
    if match:
        num_str = match.group().replace(".", "").replace(",", ".")
        try:
            return float(num_str), currency
        except ValueError:
            pass

    return None, currency


# ═══════════════════════════════════════════════════════════════════
# Lightweight standalone Playwright fetch (with minimal stealth)
# ═══════════════════════════════════════════════════════════════════

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Minimal stealth patches — just the critical detection vectors.
# Google checks: navigator.webdriver, chrome.runtime, permissions query.
# These few patches bypass the CAPTCHA without a full stealth framework.
_STEALTH_SCRIPTS = [
    # 1. Hide navigator.webdriver (the #1 detection flag)
    """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });
    """,
    # 2. Fake chrome.runtime so Google sees a real Chrome browser
    """
    window.chrome = {
        runtime: { id: undefined, connect: function(){}, sendMessage: function(){} },
        loadTimes: function(){},
        csi: function(){},
    };
    """,
    # 3. Fake permissions query (Notification permission = 'denied' in headless)
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
    """,
    # 4. Fake plugins array (headless has 0 plugins)
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
    """,
    # 5. Fake languages (headless sometimes has empty array)
    """
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
    });
    """,
]


async def _fetch_shopping_rendered(url: str) -> str | None:
    """Fetch Google Shopping page with a lightweight standalone Playwright.

    Launches a fresh Chromium, applies minimal stealth patches to avoid
    Google's CAPTCHA, navigates, extracts HTML, closes. No browser pool,
    no heavy stealth framework — just the critical anti-detection bits.
    """
    pw = None
    browser = None
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )

        # Apply minimal stealth patches before any page loads
        for script in _STEALTH_SCRIPTS:
            await context.add_init_script(script)

        page = await context.new_page()

        # Block images/fonts/media for speed
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}",
            lambda route: route.abort(),
        )

        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=20000
        )
        if not response or response.status >= 400:
            logger.warning(
                "Shopping fetch status %s",
                response.status if response else "None",
            )
            return None

        # Wait for product cards to render
        try:
            await page.wait_for_selector(
                "div.sh-dgr__content", timeout=10000
            )
        except Exception:
            try:
                await page.wait_for_selector(
                    "div.sh-pr__product-results", timeout=5000
                )
            except Exception:
                logger.warning("Shopping product cards did not render")

        # Let remaining JS settle
        await asyncio.sleep(1.5)

        # Accept cookies if prompt appears
        try:
            accept_btn = page.locator(
                "button:has-text('Accept all'), "
                "button:has-text('Accept'), "
                "button:has-text('I agree')"
            ).first
            if await accept_btn.is_visible(timeout=1000):
                await accept_btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        html = await page.content()
        logger.info(
            "Shopping lightweight fetch: %d chars, %d divs",
            len(html),
            html.count("<div"),
        )
        return html

    except Exception as e:
        logger.warning("Shopping lightweight fetch failed: %s", e)
        return None
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
# HTML parser — selectors from confirmed working Selenium script
# ═══════════════════════════════════════════════════════════════════


def _parse_shopping_html(
    html: str, query: str, page: int
) -> GoogleShoppingResponse:
    """Parse rendered Google Shopping HTML into structured product data."""
    soup = BeautifulSoup(html, "lxml")

    products = _parse_product_cards(soup, page)
    related = _parse_shopping_related(soup)
    total_results = _parse_shopping_total(soup)

    return GoogleShoppingResponse(
        query=query,
        total_results=total_results,
        time_taken=0,
        products=products,
        related_searches=related,
    )


def _parse_product_cards(
    soup: BeautifulSoup, page: int
) -> list[GoogleShoppingProduct]:
    """Extract product cards from rendered Google Shopping HTML."""
    products: list[GoogleShoppingProduct] = []
    offset = (page - 1) * _RESULTS_PER_PAGE

    # Primary container: sh-dgr__content (confirmed by Selenium script)
    containers = soup.select("div.sh-dgr__content")

    # Fallbacks
    if not containers:
        containers = soup.select("div.sh-dgr__gr-auto")
    if not containers:
        containers = soup.select("div.sh-dlr__list-result")
    if not containers:
        containers = soup.select("div.KZmu8e")

    logger.info("Found %d product containers", len(containers))

    for i, card in enumerate(containers):
        try:
            product = _parse_single_product(card, offset + i + 1)
            if product:
                products.append(product)
        except Exception as e:
            logger.debug("Failed to parse shopping product %d: %s", i, e)
            continue

    return products


def _parse_single_product(
    card, position: int
) -> GoogleShoppingProduct | None:
    """Extract data from a single product card.

    Selectors based on confirmed working Selenium script:
    - Title: .C7Lkve .EI11Pd .tAxDx
    - Price: .XrAfOe .kHxwFf .QIrs8 span
    - Merchant: .aULzUe.IuHnof
    - Shipping: .bONr3b .vEjMR
    - Image: .ArOc1c img
    - URL: .eaGTj.mQaFGe.shntl a
    """

    # === Title ===
    title = None
    for sel in [
        "h3.tAxDx",
        ".C7Lkve .EI11Pd .tAxDx",
        "h3.sh-np__product-title",
        "h3",
    ]:
        el = card.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            if title:
                break
    if not title:
        return None

    # === URL ===
    url = ""
    for sel in [
        "a.shntl",
        "a.Lq5OHe",
        "a[href*='/shopping/product']",
        "a[href*='/url?']",
        "a[href]",
    ]:
        el = card.select_one(sel)
        if el:
            href = el.get("href", "")
            if href and not href.startswith("#") and not href.startswith("/search"):
                if "/url?q=" in href:
                    url = href.split("/url?q=")[1].split("&")[0]
                elif href.startswith("/"):
                    url = f"https://www.google.com{href}"
                else:
                    url = href
                break
    if not url:
        return None

    # === Price ===
    price_text = None
    for sel in [
        ".kHxwFf .QIrs8 span",
        "span.a8Pemb",
        "span.kHxwFf",
        "span.HRLxBb",
    ]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and re.search(r"\d", text):
                price_text = text
                break

    if not price_text:
        for el in card.select("span, b"):
            text = el.get_text(strip=True)
            if text and re.match(r"^[\$€£¥₹][\d,]+\.?\d*$", text.strip()):
                price_text = text
                break

    price_value, currency = _parse_price_string(price_text or "")

    # === Original price (strikethrough) ===
    original_price = None
    for sel in ["span.T14wmb", "span.Hlkkvb", "s"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and re.search(r"\d", text):
                original_price = text
                break

    # === Merchant ===
    merchant = None
    for sel in [
        ".aULzUe.IuHnof",
        "div.aULzUe",
        "div.E5ocAb",
        "span.IuHnof",
    ]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) < 100:
                merchant = text
                break

    # === Rating ===
    rating = None
    for sel in ["span.Rsc7Yb", "span.yi40Hd"]:
        el = card.select_one(sel)
        if el:
            try:
                rating = float(el.get_text(strip=True))
                break
            except ValueError:
                continue

    if rating is None:
        for el in card.select("[aria-label]"):
            label = el.get("aria-label", "")
            match = re.search(r"(\d+\.?\d*)\s*(out of|stars|/)\s*5", label, re.I)
            if match:
                try:
                    rating = float(match.group(1))
                    break
                except ValueError:
                    continue

    # === Review count ===
    review_count = None
    for sel in ["span.QIrs8", "span.NzUzee", "span.Wphh3d"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            match = re.search(r"[\d,]+", text.replace("(", "").replace(")", ""))
            if match:
                try:
                    review_count = int(match.group().replace(",", ""))
                    break
                except ValueError:
                    continue

    # === Image ===
    image_url = None
    for sel in [
        ".ArOc1c img",
        "img.TL92Hc",
        "img.sh-img__image",
        "img[data-src]",
        "img[src]",
    ]:
        el = card.select_one(sel)
        if el:
            src = el.get("data-src") or el.get("src") or ""
            if src and not src.startswith("data:"):
                image_url = src
                break

    # === Shipping ===
    shipping = None
    for sel in [
        ".bONr3b .vEjMR",
        "span.vEjMR",
        "div.dD8iuc",
    ]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text:
                shipping = text
                break

    if not shipping:
        card_text = card.get_text(separator=" ", strip=True).lower()
        if "free shipping" in card_text or "free delivery" in card_text:
            shipping = "Free shipping"

    # === Badge ===
    badge = None
    for sel in ["span.Ib8pOd", "span.KkSFGe"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                badge = text
                break

    return GoogleShoppingProduct(
        position=position,
        title=title,
        url=url,
        image_url=image_url,
        price=price_text,
        price_value=price_value,
        currency=currency,
        original_price=original_price,
        merchant=merchant,
        rating=rating,
        review_count=review_count,
        shipping=shipping,
        badge=badge,
    )


def _parse_shopping_related(soup: BeautifulSoup) -> list[RelatedSearch]:
    related: list[RelatedSearch] = []
    seen: set[str] = set()
    for sel in ["div#botstuff a", "a.k8XOCe", "div.s75CSd a"]:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            href = el.get("href", "")
            if (
                text
                and 2 < len(text) < 100
                and text.lower() not in seen
                and ("/search?" in href or not href)
            ):
                seen.add(text.lower())
                related.append(RelatedSearch(query=text))
    return related


def _parse_shopping_total(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("div#result-stats")
    return el.get_text(strip=True) if el else None


# ═══════════════════════════════════════════════════════════════════
# SearXNG fallback
# ═══════════════════════════════════════════════════════════════════


async def _search_via_searxng_shopping(
    query: str, num: int, page: int, lang: str
) -> GoogleShoppingResponse | None:
    """Fetch shopping results from SearXNG.

    Tries the 'shopping' category first. If it returns 0 results (engines
    not configured), falls back to 'general' category with 'buy <query>'
    to get product-like results.
    """
    if not settings.SEARXNG_URL:
        return None

    base_url = settings.SEARXNG_URL.rstrip("/")

    # Try shopping category first, then general as fallback
    attempts = [
        {"q": query, "format": "json", "categories": "shopping",
         "pageno": page, "language": lang},
        {"q": f"buy {query}", "format": "json", "categories": "general",
         "pageno": page, "language": lang},
    ]

    for params in attempts:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{base_url}/search", params=params)
                resp.raise_for_status()
                data = resp.json()

            results_list = data.get("results", [])
            logger.info(
                "SearXNG [%s] returned %d results for '%s'",
                params.get("categories"),
                len(results_list),
                params.get("q"),
            )

            if not results_list:
                continue

            products: list[GoogleShoppingProduct] = []
            offset = (page - 1) * num
            for i, item in enumerate(results_list[:num]):
                price_text = item.get("price", "")
                price_value, currency = _parse_price_string(str(price_text))
                products.append(
                    GoogleShoppingProduct(
                        position=offset + i + 1,
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        image_url=item.get("thumbnail") or item.get("img_src"),
                        price=str(price_text) if price_text else None,
                        price_value=price_value,
                        currency=currency,
                        merchant=item.get("engine"),
                    )
                )

            related = [
                RelatedSearch(query=s)
                for s in data.get("suggestions", [])
            ]

            if products:
                return GoogleShoppingResponse(
                    query=query, time_taken=0, products=products,
                    related_searches=related,
                )
        except Exception as e:
            logger.warning(
                "SearXNG %s search failed: %s", params.get("categories"), e
            )

    return None


# ═══════════════════════════════════════════════════════════════════
# Single-page fetcher
# ═══════════════════════════════════════════════════════════════════


async def _fetch_single_shopping_page(
    query: str,
    page: int,
    lang: str,
    country: str | None,
    sort_by: str | None,
    min_rating: int | None,
) -> GoogleShoppingResponse | None:
    """Fetch one page: lightweight Playwright → SearXNG fallback."""
    url = _build_shopping_url(
        query, _RESULTS_PER_PAGE, page, lang, country, sort_by, min_rating,
    )
    logger.info("Google Shopping page %d: %s", page, url)

    # Strategy 1: Lightweight standalone Playwright
    html = await _fetch_shopping_rendered(url)
    if html:
        html_lower = html.lower()
        if "captcha" in html_lower or "unusual traffic" in html_lower:
            logger.warning("Google CAPTCHA detected during Shopping scrape")
        else:
            try:
                result = _parse_shopping_html(html, query, page)
                if result.products:
                    return result
                logger.warning(
                    "Shopping parsed 0 products from %d chars (%d divs)",
                    len(html),
                    html.count("<div"),
                )
            except Exception as e:
                logger.warning("Shopping HTML parsing failed: %s", e)

    # Strategy 2: SearXNG fallback (no filters but works without browser)
    result = await _search_via_searxng_shopping(
        query, _RESULTS_PER_PAGE, page, lang
    )
    if result and result.products:
        logger.info(
            "Shopping via SearXNG: %d products", len(result.products)
        )
        return result

    return None


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════


async def google_shopping(
    query: str,
    num_results: int = 10,
    page: int = 1,
    language: str = "en",
    country: str | None = None,
    sort_by: str | None = None,
    min_rating: int | None = None,
) -> GoogleShoppingResponse:
    """Search Google Shopping and return structured product data.

    Uses a lightweight standalone Playwright (no browser pool) since
    Google Shopping is JS-rendered. Falls back to SearXNG.
    Filters: sort_by (price/rating/reviews), min_rating (1-4 stars).
    Results cached in Redis for 5 minutes.
    """
    start = time.time()

    # Check Redis cache
    key = _cache_key(
        query, num_results, page, language, country, sort_by, min_rating,
    )
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - start, 3)
            logger.info("Shopping cache hit for '%s'", query)
            return GoogleShoppingResponse(**data)
    except Exception:
        pass

    # Calculate pages needed
    pages_needed = min(
        _MAX_PAGES,
        (num_results + _RESULTS_PER_PAGE - 1) // _RESULTS_PER_PAGE,
    )

    all_products: list[GoogleShoppingProduct] = []
    seen_urls: set[str] = set()
    first_page_extras: dict | None = None

    for pg_offset in range(pages_needed):
        current_page = page + pg_offset

        page_result = await _fetch_single_shopping_page(
            query, current_page, language, country, sort_by, min_rating,
        )

        if not page_result or not page_result.products:
            logger.info(
                "Shopping page %d returned no products, stopping",
                current_page,
            )
            break

        # Collect products (deduplicate by URL)
        for p in page_result.products:
            normalized = p.url.rstrip("/")
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            p.position = len(all_products) + 1
            all_products.append(p)

        logger.info(
            "Shopping page %d: +%d products (total: %d)",
            current_page,
            len(page_result.products),
            len(all_products),
        )

        if pg_offset == 0:
            first_page_extras = {
                "total_results": page_result.total_results,
                "related_searches": page_result.related_searches,
            }

        if len(all_products) >= num_results:
            break

        if pg_offset < pages_needed - 1:
            await asyncio.sleep(_PAGE_DELAY)

    elapsed = round(time.time() - start, 3)

    if not all_products:
        return GoogleShoppingResponse(
            success=False, query=query, time_taken=elapsed,
        )

    all_products = all_products[:num_results]

    # Filters echo
    filters_applied: dict[str, str | float | bool] = {}
    if sort_by:
        filters_applied["sort_by"] = sort_by
    if min_rating:
        filters_applied["min_rating"] = float(min_rating)

    extras = first_page_extras or {}
    result = GoogleShoppingResponse(
        query=query,
        total_results=extras.get("total_results"),
        time_taken=elapsed,
        filters_applied=filters_applied if filters_applied else None,
        products=all_products,
        related_searches=extras.get("related_searches", []),
    )

    # Cache
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
