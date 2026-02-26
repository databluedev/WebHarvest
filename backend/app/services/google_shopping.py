"""Google Shopping scraper — fetches and parses Google Shopping results.

Strategy chain (per page):
1. SearXNG (google shopping + ebay engines) — fast, no browser
2. nodriver (undetected Chrome + Xvfb) — real headed browser, bypasses bot detection

nodriver is the async successor to undetected-chromedriver. It connects to
Chrome via CDP directly — no WebDriver protocol, no chromedriver binary.
Combined with Xvfb (virtual display), it runs a real headed browser that
passes Google's headless detection.

Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import json
import logging
import re
import shutil
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
_MAX_PAGES = 50  # effectively unlimited — stops when Google returns empty
_PAGE_DELAY = 2.0
_MAX_CONSECUTIVE_EMPTY = 2

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
# Browser fetch via nodriver (undetected Chrome + Xvfb)
# ═══════════════════════════════════════════════════════════════════


def _find_chrome_binary() -> str | None:
    """Find a usable Chrome/Chromium binary on the system."""
    candidates = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
    ]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


async def _fetch_shopping_rendered(url: str) -> str | None:
    """Fetch Google Shopping page using nodriver with Xvfb virtual display.

    Uses a real headed browser (not headless) behind a virtual framebuffer.
    This bypasses Google's headless detection while running on a server.
    nodriver connects via CDP (no WebDriver) which avoids automation detection.
    """
    display = None
    try:
        import nodriver as uc
        from pyvirtualdisplay import Display

        chrome_path = _find_chrome_binary()
        if not chrome_path:
            logger.warning("No Chrome/Chromium binary found for nodriver")
            return None

        logger.info("nodriver using browser: %s", chrome_path)

        # Start virtual display (Xvfb) for headed mode
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        logger.info("Xvfb started on display :%s", display.display)

        browser = await uc.start(
            headless=False,
            browser_executable_path=chrome_path,
            sandbox=False,
            lang="en-US",
            browser_args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,1080",
                "--disable-gpu",
            ],
        )

        try:
            tab = await browser.get(url)

            # Wait for product cards to render (new Google Shopping layout)
            try:
                await tab.select("div.UC8ZCe", timeout=12)
            except Exception:
                # Try older selectors
                try:
                    await tab.select("div.sh-dgr__content", timeout=5)
                except Exception:
                    logger.warning("Shopping product cards did not render")

            # Let remaining JS settle
            await tab.sleep(2)

            # Get the full page HTML
            html = await tab.get_content()
            if not html:
                html = await tab.evaluate(
                    "document.documentElement.outerHTML"
                )

            logger.info(
                "Shopping nodriver fetch: %d chars, %d divs",
                len(html) if html else 0,
                html.count("<div") if html else 0,
            )
            return html

        finally:
            browser.stop()

    except Exception as e:
        logger.warning("Shopping nodriver fetch failed: %s", e)
        return None
    finally:
        if display:
            try:
                display.stop()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
# HTML parser — supports both new and old Google Shopping layouts
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

    # New layout (2024+): div.UC8ZCe.QS8Cxb
    containers = soup.select("div.UC8ZCe.QS8Cxb")

    if containers:
        logger.info("Using new Google Shopping layout (%d cards)", len(containers))
        for i, card in enumerate(containers):
            try:
                product = _parse_new_product(card, offset + i + 1)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("Failed to parse new product card %d: %s", i, e)
                continue
        return products

    # Old layout fallback: sh-dgr__content
    for sel in [
        "div.sh-dgr__content",
        "div.sh-dgr__gr-auto",
        "div.sh-dlr__list-result",
        "div.KZmu8e",
    ]:
        containers = soup.select(sel)
        if containers:
            break

    logger.info("Using old Google Shopping layout (%d cards)", len(containers))

    for i, card in enumerate(containers):
        try:
            product = _parse_old_product(card, offset + i + 1)
            if product:
                products.append(product)
        except Exception as e:
            logger.debug("Failed to parse old product card %d: %s", i, e)
            continue

    return products


def _parse_new_product(
    card, position: int
) -> GoogleShoppingProduct | None:
    """Parse a product card from the new Google Shopping layout (2024+).

    New selectors discovered from live HTML:
    - Title: div.gkQHve
    - Price: div.FG68Ac
    - Merchant: span.Z9qvte
    - Rating: span.yi40Hd
    - Rating+Reviews: [aria-label*='Rated']
    - Shipping: span.ybnj7e
    - Badge: div.OWYldd
    - Image: img.VeBrne
    """

    # === Title ===
    title = None
    title_el = card.select_one("div.gkQHve")
    if title_el:
        title = title_el.get_text(strip=True)

    if not title:
        # Fallback: extract from div.V5fewe or div.PhALMc
        for sel in ["div.V5fewe", "div.PhALMc"]:
            el = card.select_one(sel)
            if el:
                texts = list(el.stripped_strings)
                # Title is usually the longest string that's not a price/badge
                for t in texts:
                    if (
                        len(t) > 5
                        and not re.match(r"^[\$€£¥₹₩]", t)
                        and t not in ("LOW PRICE", "SALE", "GREAT PRICE")
                        and "% OFF" not in t
                        and "% off" not in t
                    ):
                        title = t
                        break
                if title:
                    break

    if not title:
        return None

    # === Price ===
    price_text = None
    original_price = None

    price_el = card.select_one("div.FG68Ac")
    if price_el:
        # Best: use aria-label for precise price
        aria = price_el.get("aria-label", "")
        if aria:
            # "Current price: ₹799.  68% off maximum retail price: ₹2,499."
            curr_match = re.search(
                r"Current price:\s*([₹$€£¥][\d,]+\.?\d*)", aria
            )
            if curr_match:
                price_text = curr_match.group(1).rstrip(".")
            orig_match = re.search(
                r"(?:retail|original|was)\s*(?:price)?:?\s*([₹$€£¥][\d,]+\.?\d*)",
                aria, re.I,
            )
            if orig_match:
                original_price = orig_match.group(1).rstrip(".")

        # Fallback: use dedicated span selectors
        if not price_text:
            curr_span = price_el.select_one("span.lmQWe")
            if curr_span:
                price_text = curr_span.get_text(strip=True)
            orig_span = price_el.select_one("span.Y1xxFf")
            if orig_span:
                original_price = orig_span.get_text(strip=True)

        # Last fallback: parse the combined text
        if not price_text:
            full = price_el.get_text(strip=True)
            match = re.match(r"^([₹$€£¥][,\d]+\.?\d*)", full)
            if match:
                price_text = match.group(1)
                remainder = full[len(price_text):]
                orig = re.search(r"([₹$€£¥][,\d]+\.?\d*)", remainder)
                if orig:
                    original_price = orig.group(1)

    price_value, currency = _parse_price_string(price_text or "")

    # === Merchant ===
    merchant = None
    merchant_el = card.select_one("span.Z9qvte")
    if merchant_el:
        merchant = merchant_el.get_text(strip=True)

    # === Rating & Reviews ===
    rating = None
    review_count = None

    rating_el = card.select_one("span.yi40Hd")
    if rating_el:
        try:
            rating = float(rating_el.get_text(strip=True))
        except ValueError:
            pass

    # Get review count from aria-label
    rated_el = card.select_one("[aria-label*='Rated']")
    if not rated_el:
        rated_el = card.select_one("[aria-label*='rated']")
    if rated_el:
        label = rated_el.get("aria-label", "")
        # "Rated 3.9 out of 5. 10 reviews." or "Rated 4.8 out of 5, 30K reviews"
        if rating is None:
            r_match = re.search(r"Rated\s+([\d.]+)", label, re.I)
            if r_match:
                try:
                    rating = float(r_match.group(1))
                except ValueError:
                    pass

        rv_match = re.search(r"([\d,.]+K?)\s*(?:user\s+)?reviews?", label, re.I)
        if rv_match:
            rv_str = rv_match.group(1).replace(",", "")
            if rv_str.endswith("K"):
                try:
                    review_count = int(float(rv_str[:-1]) * 1000)
                except ValueError:
                    pass
            else:
                try:
                    review_count = int(rv_str)
                except ValueError:
                    pass

    # === Shipping ===
    shipping = None
    ship_el = card.select_one("span.ybnj7e")
    if ship_el:
        shipping = ship_el.get_text(strip=True)

    if not shipping:
        card_text = card.get_text(separator=" ", strip=True).lower()
        if "free shipping" in card_text or "free delivery" in card_text:
            shipping = "Free shipping"

    # === Badge ===
    badge = None
    badge_el = card.select_one("div.OWYldd")
    if badge_el:
        badge = badge_el.get_text(strip=True)

    # === Image ===
    image_url = None
    img_el = card.select_one("img.VeBrne")
    if img_el:
        src = img_el.get("src", "")
        if src and not src.startswith("data:"):
            image_url = src
        # For base64 images, we still include them (they're valid data URIs)
        elif src and src.startswith("data:image/"):
            image_url = src

    if not image_url:
        img_el = card.select_one("img.XNo5Ab")
        if img_el:
            src = img_el.get("src", "")
            if src:
                image_url = src

    # === URL (no <a> tags in new layout — construct from title) ===
    url = (
        f"https://www.google.com/search?tbm=shop&q={quote_plus(title)}"
    )

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


def _parse_old_product(
    card, position: int
) -> GoogleShoppingProduct | None:
    """Parse product from old Google Shopping layout (pre-2024).

    Kept for backwards compatibility in case Google serves old layout.
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
        url = f"https://www.google.com/search?tbm=shop&q={quote_plus(title)}"

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

    # === Original price ===
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
    """Fetch shopping results from SearXNG (shopping category only)."""
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

        results_list = data.get("results", [])
        logger.info(
            "SearXNG shopping returned %d results for '%s'",
            len(results_list),
            query,
        )

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

        related = [RelatedSearch(query=s) for s in data.get("suggestions", [])]

        if products:
            return GoogleShoppingResponse(
                query=query, time_taken=0, products=products,
                related_searches=related,
            )
    except Exception as e:
        logger.warning("SearXNG shopping search failed: %s", e)

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
    """Fetch one page: SearXNG first (fast) → nodriver fallback."""
    logger.info("Google Shopping page %d for '%s'", page, query)

    # Strategy 1: SearXNG (fast, no browser cost)
    result = await _search_via_searxng_shopping(
        query, _RESULTS_PER_PAGE, page, lang
    )
    if result and result.products:
        logger.info(
            "Shopping via SearXNG: %d products", len(result.products)
        )
        return result

    # Strategy 2: nodriver (undetected Chrome + Xvfb)
    url = _build_shopping_url(
        query, _RESULTS_PER_PAGE, page, lang, country, sort_by, min_rating,
    )
    logger.info("SearXNG had no results, trying nodriver: %s", url)

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

    SearXNG primary (fast), nodriver fallback (undetected Chrome + Xvfb).
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

    # Paginate until Google returns no more results
    all_products: list[GoogleShoppingProduct] = []
    seen_urls: set[str] = set()
    first_page_extras: dict | None = None
    consecutive_empty = 0

    for pg_offset in range(_MAX_PAGES):
        current_page = page + pg_offset

        page_result = await _fetch_single_shopping_page(
            query, current_page, language, country, sort_by, min_rating,
        )

        if not page_result or not page_result.products:
            consecutive_empty += 1
            logger.info(
                "Shopping page %d returned no products (%d consecutive empty)",
                current_page, consecutive_empty,
            )
            if consecutive_empty >= _MAX_CONSECUTIVE_EMPTY:
                break
            continue

        consecutive_empty = 0

        # Collect products (deduplicate by title since URLs are constructed)
        new_count = 0
        for p in page_result.products:
            dedup_key = p.title.lower().strip()
            if dedup_key in seen_urls:
                continue
            seen_urls.add(dedup_key)
            p.position = len(all_products) + 1
            all_products.append(p)
            new_count += 1

        logger.info(
            "Shopping page %d: +%d new products (total: %d unique)",
            current_page, new_count, len(all_products),
        )

        if pg_offset == 0:
            first_page_extras = {
                "total_results": page_result.total_results,
                "related_searches": page_result.related_searches,
            }

        # If page returned all dupes, Google is recycling — stop
        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= _MAX_CONSECUTIVE_EMPTY:
                break

        if pg_offset < _MAX_PAGES - 1:
            await asyncio.sleep(_PAGE_DELAY)

    elapsed = round(time.time() - start, 3)

    if not all_products:
        return GoogleShoppingResponse(
            success=False, query=query, time_taken=elapsed,
        )

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
