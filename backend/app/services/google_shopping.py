"""Google Shopping scraper — fetches and parses Google Shopping results.

Strategy chain:
1. Direct Google Shopping scrape (curl_cffi + BS4 parser) — supports ALL filters
2. SearXNG shopping category (fallback for unfiltered queries)

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
from app.services.google_serp import _fetch_google_html  # Reuse TLS fetch

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_RESULTS_PER_PAGE = 10
_MAX_PAGES = 10
_PAGE_DELAY = 1.0

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
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    min_rating: int | None,
    free_shipping: bool,
) -> str:
    raw = (
        f"shop|{query}|{num}|{page}|{lang}|{country or ''}"
        f"|{sort_by or ''}|{min_price}|{max_price}"
        f"|{condition or ''}|{min_rating or ''}|{free_shipping}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:shopping:{h}"


# ═══════════════════════════════════════════════════════════════════
# URL builder with filters
# ═══════════════════════════════════════════════════════════════════


def _build_shopping_url(
    query: str,
    num: int = 10,
    page: int = 1,
    lang: str = "en",
    country: str | None = None,
    sort_by: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    condition: str | None = None,
    min_rating: int | None = None,
    free_shipping: bool = False,
) -> str:
    """Build a Google Shopping URL with all filter parameters."""
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

    # Sort order
    sort_map = {
        "price_low": "p_ord:p",
        "price_high": "p_ord:pd",
        "rating": "p_ord:r",
        "reviews": "p_ord:rv",
    }
    if sort_by and sort_by in sort_map:
        tbs_parts.append(sort_map[sort_by])

    # Price range
    if min_price is not None or max_price is not None:
        tbs_parts.append("mr:1")
        tbs_parts.append("price:1")
        if min_price is not None:
            tbs_parts.append(f"ppr_min:{int(min_price)}")
        if max_price is not None:
            tbs_parts.append(f"ppr_max:{int(max_price)}")

    # Condition
    if condition == "new":
        tbs_parts.append("mr:1")
        tbs_parts.append("new:1")
    elif condition == "used":
        tbs_parts.append("mr:1")
        tbs_parts.append("used:1")

    # Minimum rating
    if min_rating and 1 <= min_rating <= 4:
        tbs_parts.append("mr:1")
        tbs_parts.append(f"avg_rating:{min_rating}00")

    # Free shipping
    if free_shipping:
        tbs_parts.append("mr:1")
        tbs_parts.append("ship:1")

    if tbs_parts:
        # Deduplicate (mr:1 can appear multiple times)
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
    """Extract numeric price and currency code from a price string.

    Returns (price_value, currency_code).
    Examples: "$29.99" → (29.99, "USD"), "€1,299.00" → (1299.0, "EUR")
    """
    if not text:
        return None, None

    text = text.strip()

    # Detect currency
    currency = None
    for symbol, code in _CURRENCY_MAP.items():
        if symbol in text:
            currency = code
            break

    # Extract numeric value
    # Handle formats: 1,299.99 or 1.299,99 (European)
    # First try standard format (comma as thousands, dot as decimal)
    match = re.search(r"[\d,]+\.?\d*", text.replace(" ", ""))
    if match:
        num_str = match.group().replace(",", "")
        try:
            return float(num_str), currency
        except ValueError:
            pass

    # Try European format (dot as thousands, comma as decimal)
    match = re.search(r"[\d.]+,\d{2}", text.replace(" ", ""))
    if match:
        num_str = match.group().replace(".", "").replace(",", ".")
        try:
            return float(num_str), currency
        except ValueError:
            pass

    return None, currency


# ═══════════════════════════════════════════════════════════════════
# HTML parser for Google Shopping
# ═══════════════════════════════════════════════════════════════════


def _parse_shopping_html(
    html: str, query: str, page: int
) -> GoogleShoppingResponse:
    """Parse Google Shopping SERP HTML into structured product data."""
    soup = BeautifulSoup(html, "lxml")

    products = _parse_product_cards(soup, page)
    related = _parse_shopping_related(soup)
    total_results = _parse_shopping_total(soup)

    return GoogleShoppingResponse(
        query=query,
        total_results=total_results,
        time_taken=0,  # Set by caller
        products=products,
        related_searches=related,
    )


def _parse_product_cards(
    soup: BeautifulSoup, page: int
) -> list[GoogleShoppingProduct]:
    """Extract product cards from Google Shopping HTML."""
    products: list[GoogleShoppingProduct] = []
    offset = (page - 1) * _RESULTS_PER_PAGE

    # Try multiple container selectors (Google changes these)
    containers = []
    for sel in [
        "div.sh-dgr__gr-auto",  # Grid product cards
        "div.sh-dgr__content",  # Shopping grid items
        "div.KZmu8e",  # Newer product wrapper
        "div.i0X6df",  # Alternative wrapper
        "div.sh-dlr__list-result",  # List view items
        "div.xcR77",  # Compact product cards
    ]:
        containers = soup.select(sel)
        if containers:
            break

    # Broader fallback: find any div with product-like data attributes
    if not containers:
        containers = soup.select("div[data-docid], div[data-hveid]")

    for i, card in enumerate(containers):
        try:
            product = _parse_single_product(card, offset + i + 1)
            if product:
                products.append(product)
        except Exception as e:
            logger.debug(f"Failed to parse shopping product {i}: {e}")
            continue

    return products


def _parse_single_product(
    card, position: int
) -> GoogleShoppingProduct | None:
    """Extract data from a single product card."""

    # === Title ===
    title = None
    for sel in [
        "h3.tAxDx",
        "h3.sh-np__product-title",
        "a.Lq5OHe h3",
        "div.rgHvZc a",
        "h4",
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
        "a.Lq5OHe",
        "a.shntl",
        "a[href*='/shopping/product']",
        "a[href*='/url?']",
        "a[href]",
    ]:
        el = card.select_one(sel)
        if el:
            href = el.get("href", "")
            if href and not href.startswith("#") and not href.startswith("/search"):
                # Handle Google redirect URLs
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
        "span.a8Pemb",
        "span.kHxwFf",
        "span.HRLxBb",
        "span.sh-dgr__content-price",
        "b",
    ]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and re.search(r"\d", text):
                price_text = text
                break

    # Fallback: find any element with a currency symbol + number
    if not price_text:
        for el in card.select("span, div"):
            text = el.get_text(strip=True)
            if text and re.match(r"^[\$€£¥₹₩][\d,]+\.?\d*$", text.strip()):
                price_text = text
                break

    price_value, currency = _parse_price_string(price_text or "")

    # === Original price (sale/strikethrough) ===
    original_price = None
    for sel in ["span.T14wmb", "span.Hlkkvb", "span.sh-dgr__content-old-price", "s"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and re.search(r"\d", text):
                original_price = text
                break

    # === Merchant ===
    merchant = None
    for sel in [
        "div.aULzUe",
        "div.E5ocAb",
        "span.IuHnof",
        "div.sh-dgr__content-seller",
        "span.zPEcBd",
    ]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) < 100:
                merchant = text
                break

    # === Rating ===
    rating = None
    for sel in ["span.Rsc7Yb", "span.yi40Hd", "div.NzUzee span"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            try:
                rating = float(text)
                break
            except ValueError:
                continue

    # Also check aria-label for rating
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
            # Extract number from "(1,234)" or "1,234 reviews"
            match = re.search(r"[\d,]+", text.replace("(", "").replace(")", ""))
            if match:
                try:
                    review_count = int(match.group().replace(",", ""))
                    break
                except ValueError:
                    continue

    # === Image ===
    image_url = None
    for sel in ["img.TL92Hc", "img.sh-img__image", "img[data-src]", "img[src]"]:
        el = card.select_one(sel)
        if el:
            src = el.get("data-src") or el.get("src") or ""
            if src and not src.startswith("data:") and "google" not in src:
                image_url = src
                break

    # === Shipping ===
    shipping = None
    for sel in ["span.vEjMR", "div.dD8iuc", "span.sh-dgr__content-shipping"]:
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text:
                shipping = text
                break
    # Check for "Free shipping" in any text
    if not shipping:
        card_text = card.get_text(separator=" ", strip=True).lower()
        if "free shipping" in card_text or "free delivery" in card_text:
            shipping = "Free shipping"

    # === Condition ===
    condition = None
    card_text_lower = card.get_text(separator=" ", strip=True).lower()
    if "refurbished" in card_text_lower:
        condition = "Refurbished"
    elif "used" in card_text_lower:
        condition = "Used"
    elif "pre-owned" in card_text_lower:
        condition = "Pre-owned"

    # === Badge ===
    badge = None
    for sel in ["span.Ib8pOd", "span.KkSFGe", "div.jBTlje"]:
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
        condition=condition,
        badge=badge,
    )


def _parse_shopping_related(soup: BeautifulSoup) -> list[RelatedSearch]:
    """Extract related searches from Shopping results."""
    related: list[RelatedSearch] = []
    seen: set[str] = set()

    for sel in ["div#botstuff a", "a.k8XOCe", "div.s75CSd a", "a.EIaa9b"]:
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
    """Extract total results text."""
    el = soup.select_one("div#result-stats")
    if el:
        return el.get_text(strip=True)
    return None


# ═══════════════════════════════════════════════════════════════════
# Strategy 1: Direct Google Shopping scrape
# ═══════════════════════════════════════════════════════════════════


async def _scrape_shopping_page(
    query: str,
    page: int,
    lang: str,
    country: str | None,
    sort_by: str | None,
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    min_rating: int | None,
    free_shipping: bool,
) -> GoogleShoppingResponse | None:
    """Fetch one page of Google Shopping results via direct scrape."""
    url = _build_shopping_url(
        query,
        _RESULTS_PER_PAGE,
        page,
        lang,
        country,
        sort_by,
        min_price,
        max_price,
        condition,
        min_rating,
        free_shipping,
    )
    logger.info(f"Google Shopping scrape page {page}: {url}")

    html = await _fetch_google_html(url)
    if not html:
        return None

    html_lower = html.lower()
    if "captcha" in html_lower or "unusual traffic" in html_lower:
        logger.warning("Google CAPTCHA detected during Shopping scrape")
        return None

    try:
        result = _parse_shopping_html(html, query, page)
        if result.products:
            return result
        logger.warning(
            f"Shopping scrape parsed 0 products from {len(html)} chars HTML"
        )
    except Exception as e:
        logger.warning(f"Google Shopping HTML parsing failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════
# Strategy 2: SearXNG shopping (unfiltered fallback)
# ═══════════════════════════════════════════════════════════════════


async def _search_via_searxng_shopping(
    query: str, num: int, page: int, lang: str
) -> GoogleShoppingResponse | None:
    """Fetch shopping results from SearXNG."""
    if not settings.SEARXNG_URL:
        return None

    base_url = settings.SEARXNG_URL.rstrip("/")
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "categories": "shopping",
        "pageno": page,
        "language": lang,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        products: list[GoogleShoppingProduct] = []
        offset = (page - 1) * num
        for i, item in enumerate(data.get("results", [])[:num]):
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
            RelatedSearch(query=s) for s in data.get("suggestions", [])
        ]

        if products:
            return GoogleShoppingResponse(
                query=query,
                time_taken=0,
                products=products,
                related_searches=related,
            )
    except Exception as e:
        logger.warning(f"SearXNG shopping search failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════
# Single-page fetcher
# ═══════════════════════════════════════════════════════════════════


def _has_filters(
    sort_by: str | None,
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    min_rating: int | None,
    free_shipping: bool,
) -> bool:
    """Check if any filters are applied."""
    return bool(
        sort_by or min_price is not None or max_price is not None
        or condition or min_rating or free_shipping
    )


async def _fetch_single_shopping_page(
    query: str,
    page: int,
    lang: str,
    country: str | None,
    sort_by: str | None,
    min_price: float | None,
    max_price: float | None,
    condition: str | None,
    min_rating: int | None,
    free_shipping: bool,
) -> GoogleShoppingResponse | None:
    """Fetch one page using the strategy chain.

    If filters are applied → direct scrape only (SearXNG can't pass filters).
    If no filters → SearXNG first, then direct scrape.
    """
    has_f = _has_filters(
        sort_by, min_price, max_price, condition, min_rating, free_shipping
    )

    if not has_f:
        # Try SearXNG first (faster, no filter needed)
        result = await _search_via_searxng_shopping(
            query, _RESULTS_PER_PAGE, page, lang
        )
        if result and result.products:
            return result

    # Direct scrape (supports all filters)
    return await _scrape_shopping_page(
        query, page, lang, country, sort_by,
        min_price, max_price, condition, min_rating, free_shipping,
    )


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
    min_price: float | None = None,
    max_price: float | None = None,
    condition: str | None = None,
    min_rating: int | None = None,
    free_shipping: bool = False,
) -> GoogleShoppingResponse:
    """Search Google Shopping with filters and return structured product data.

    Fetches multiple pages when num_results > 10.
    Results are cached in Redis for 5 minutes.
    """
    start = time.time()

    # Check Redis cache
    key = _cache_key(
        query, num_results, page, language, country,
        sort_by, min_price, max_price, condition, min_rating, free_shipping,
    )
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - start, 3)
            logger.info(f"Shopping cache hit for '{query}'")
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
            query, current_page, language, country,
            sort_by, min_price, max_price, condition, min_rating, free_shipping,
        )

        if not page_result or not page_result.products:
            logger.info(
                f"Shopping page {current_page} returned no products, stopping"
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
            f"Shopping page {current_page}: +{len(page_result.products)} "
            f"products (total: {len(all_products)})"
        )

        # Save extras from first page
        if pg_offset == 0:
            first_page_extras = {
                "total_results": page_result.total_results,
                "related_searches": page_result.related_searches,
            }

        # Have enough?
        if len(all_products) >= num_results:
            break

        # Delay between pages
        if pg_offset < pages_needed - 1:
            await asyncio.sleep(_PAGE_DELAY)

    elapsed = round(time.time() - start, 3)

    if not all_products:
        return GoogleShoppingResponse(
            success=False,
            query=query,
            time_taken=elapsed,
        )

    # Trim to requested count
    all_products = all_products[:num_results]

    # Build filters_applied echo
    filters_applied: dict[str, str | float | bool] = {}
    if sort_by:
        filters_applied["sort_by"] = sort_by
    if min_price is not None:
        filters_applied["min_price"] = min_price
    if max_price is not None:
        filters_applied["max_price"] = max_price
    if condition:
        filters_applied["condition"] = condition
    if min_rating:
        filters_applied["min_rating"] = float(min_rating)
    if free_shipping:
        filters_applied["free_shipping"] = True

    extras = first_page_extras or {}
    result = GoogleShoppingResponse(
        query=query,
        total_results=extras.get("total_results"),
        time_taken=elapsed,
        filters_applied=filters_applied if filters_applied else None,
        products=all_products,
        related_searches=extras.get("related_searches", []),
    )

    # Cache the result
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
