"""Google Finance scraper — HTTP-only with AF_initDataCallback parsing.

Strategy chain:
1. curl_cffi with Chrome TLS impersonation (fastest, HTTP-only)
2. httpx fallback (if curl_cffi unavailable)

Market overview page: https://www.google.com/finance/?hl=en
Quote page:           https://www.google.com/finance/quote/AAPL:NASDAQ?hl=en

Data is embedded in AF_initDataCallback({key:'ds:N', data:...}) blocks.

Market overview blocks:
  ds:5 — Market indexes by section (US, Europe, Asia, Currencies, Crypto, Futures)
  ds:6 — Most active stocks (with volume)
  ds:3 — Top gainers and losers
  ds:7 — Market news
  ds:0 — Trending stocks

Quote page blocks:
  ds:2/ds:17 — Stock summary (price, change, prev close)
  ds:6       — Extended quote (includes after-hours data)
  ds:12      — Similar/related stocks
  ds:3/ds:4  — Stock-specific news

Stock array format (27 elements):
  [0]  mid (freebase-style ID)
  [1]  [ticker, exchange]
  [2]  name
  [3]  type: 0=stock, 1=index, 3=currency/crypto, 4=commodity
  [4]  currency (null for indexes)
  [5]  [price, change, pct_change, ...]
  [7]  previous_close
  [8]  color
  [9]  country
  [12] timezone
  [15] after-hours price data (quote page only)
  [21] ticker:exchange string

Results are cached in Redis for 2 minutes.
"""

import hashlib
import json
import logging
import re
import time

import httpx

from app.config import settings
from app.schemas.data_google import (
    GoogleFinanceMarketResponse,
    GoogleFinanceNewsArticle,
    GoogleFinancePriceMovement,
    GoogleFinanceQuoteResponse,
    GoogleFinanceStock,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # 2 minutes — finance data changes fast

_GOOGLE_HEADERS = {
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

# Section ID → display name (from Google Finance market overview tabs)
_SECTION_ID_MAP = {
    1: "US",
    2: "Europe",
    4: "Currencies",
    5: "Crypto",
    7: "Futures",
    8: "Asia",
}


# ═══════════════════════════════════════════════════════════════════
#  Cache
# ═══════════════════════════════════════════════════════════════════


def _cache_key(endpoint: str, query: str, language: str) -> str:
    raw = f"finance:{endpoint}|{query}|{language}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:finance:{h}"


# ═══════════════════════════════════════════════════════════════════
#  HTTP fetchers
# ═══════════════════════════════════════════════════════════════════


async def _fetch_via_curl_cffi(url: str) -> str | None:
    """Fetch with curl_cffi — best TLS fingerprint for Google."""
    try:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                headers=_GOOGLE_HEADERS,
                timeout=20,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            logger.warning("Google Finance curl_cffi returned %s", resp.status_code)
    except Exception as e:
        logger.warning("curl_cffi Google Finance fetch failed: %s", e)
    return None


async def _fetch_via_httpx(url: str) -> str | None:
    """Fetch with httpx — fallback if curl_cffi unavailable."""
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=_GOOGLE_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning("httpx Google Finance fetch failed: %s", e)
    return None


async def _fetch_html(url: str) -> str | None:
    """Try all strategies in order: curl_cffi → httpx."""
    html = await _fetch_via_curl_cffi(url)
    if html and "AF_initDataCallback" in html:
        return html

    html = await _fetch_via_httpx(url)
    if html and "AF_initDataCallback" in html:
        return html

    return None


# ═══════════════════════════════════════════════════════════════════
#  AF_initDataCallback parser
# ═══════════════════════════════════════════════════════════════════

_AF_PATTERN = re.compile(
    r"AF_initDataCallback\s*\(\s*\{key:\s*'([^']+)',\s*"
    r"(?:hash:\s*'[^']*',\s*)?(?:isError:\s*(?:true|false)\s*,\s*)?"
    r"data:(.*?)\}\s*\)\s*;",
    re.DOTALL,
)


def _extract_af_blocks(html: str) -> dict[str, str]:
    """Extract all AF_initDataCallback blocks as {key: raw_data_string}."""
    return dict(_AF_PATTERN.findall(html))


def _parse_af_data(raw: str) -> list | None:
    """Parse an AF_initDataCallback data string to JSON."""
    raw = raw.strip()
    raw = re.sub(r",\s*sideChannel:\s*\{[^}]*\}\s*$", "", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════


def _safe(arr: list | None, idx: int, default=None):
    """Safely index a list."""
    if arr is None or not isinstance(arr, list) or idx >= len(arr) or idx < 0:
        return default
    val = arr[idx]
    return val if val is not None else default


def _format_price(value, currency: str | None = None) -> str:
    """Format price with currency symbol."""
    if value is None:
        return ""
    # Ensure numeric
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            return str(value)
    # Currency symbol map
    symbols = {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "BRL": "R$", "AUD": "A$", "CAD": "C$",
    }
    sym = symbols.get(currency, "")
    formatted = f"{value:,.2f}"
    return f"{sym}{formatted}" if sym else formatted


def _format_change(change, currency: str | None = None) -> str:
    """Format price change with +/- sign and currency."""
    if change is None:
        return ""
    if not isinstance(change, (int, float)):
        try:
            change = float(change)
        except (ValueError, TypeError):
            return str(change)
    symbols = {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "BRL": "R$", "AUD": "A$", "CAD": "C$",
    }
    sym = symbols.get(currency, "")
    prefix = "+" if change > 0 else "-"
    formatted = f"{abs(change):,.2f}"
    return f"{prefix}{sym}{formatted}"


def _format_pct(pct: float | None) -> str:
    """Format percentage change."""
    if pct is None:
        return ""
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def _parse_stock_entry(
    entry: list,
    currency_override: str | None = None,
) -> GoogleFinanceStock | None:
    """Parse a single stock array into a GoogleFinanceStock."""
    if not entry or not isinstance(entry, list) or len(entry) < 6:
        return None

    ticker_pair = _safe(entry, 1)
    name = _safe(entry, 2, "")
    currency = _safe(entry, 4) or currency_override
    price_data = _safe(entry, 5)
    prev_close = _safe(entry, 7)

    # Build stock ID — ticker_pair may be None for currencies/crypto
    if ticker_pair and isinstance(ticker_pair, list) and len(ticker_pair) >= 2:
        stock_id = f"{ticker_pair[0]}:{ticker_pair[1]}"
    elif _safe(entry, 21):
        # Fallback to [21] which has "USD-INR", "BTC-INR" etc.
        stock_id = str(entry[21])
    else:
        return None

    # Price
    price_val = _safe(price_data, 0) if price_data else None
    change_val = _safe(price_data, 1) if price_data else None
    pct_val = _safe(price_data, 2) if price_data else None

    # Build price movement
    movement = None
    if change_val is not None and pct_val is not None:
        movement = GoogleFinancePriceMovement(
            percentage=_format_pct(pct_val),
            value=_format_change(change_val, currency),
            movement="up" if change_val > 0 else "down",
        )

    return GoogleFinanceStock(
        stock=stock_id,
        link=f"https://www.google.com/finance/quote/{stock_id}",
        name=name,
        price=_format_price(price_val, currency),
        price_movement=movement,
        currency=currency,
        previous_close=_format_price(prev_close, currency) if prev_close else None,
    )


def _parse_news_entry(entry: list) -> GoogleFinanceNewsArticle | None:
    """Parse a news entry from ds:7 or ds:3/ds:4."""
    if not entry or not isinstance(entry, list) or len(entry) < 4:
        return None

    url = _safe(entry, 0)
    title = _safe(entry, 1)
    source = _safe(entry, 2)
    thumbnail = _safe(entry, 3)
    timestamp = _safe(entry, 4)
    snippet = _safe(entry, 16) if len(entry) > 16 else None

    if not url or not title:
        return None

    return GoogleFinanceNewsArticle(
        title=title,
        url=url,
        source=source,
        thumbnail=thumbnail,
        snippet=snippet,
        published_timestamp=timestamp,
    )


# ═══════════════════════════════════════════════════════════════════
#  Market Overview parser
# ═══════════════════════════════════════════════════════════════════


def _parse_market_overview(blocks: dict[str, str]) -> GoogleFinanceMarketResponse:
    """Parse market overview AF blocks into structured response."""
    markets: dict[str, list[GoogleFinanceStock]] = {}
    market_trends: dict[str, list[GoogleFinanceStock]] = {}
    news: list[GoogleFinanceNewsArticle] = []

    # --- ds:5 — Market indexes by section ---
    ds5 = _parse_af_data(blocks.get("ds:5", ""))
    if ds5 and isinstance(ds5, list) and len(ds5) > 0:
        sections = _safe(ds5, 0, [])
        for section in sections:
            if not isinstance(section, list) or len(section) < 2:
                continue
            section_id = _safe(section, 0)
            section_name = _SECTION_ID_MAP.get(section_id, f"Other_{section_id}")
            groups = _safe(section, 1, [])

            stocks_list: list[GoogleFinanceStock] = []
            for group in groups:
                if not isinstance(group, list) or len(group) < 2:
                    continue
                entries = _safe(group, 1)
                if not entries or not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, list):
                        continue
                    # Skip non-stock entries (like "see more" links)
                    if len(entry) < 6:
                        continue
                    stock = _parse_stock_entry(entry)
                    if stock:
                        stocks_list.append(stock)

            if stocks_list:
                markets[section_name] = stocks_list

    # --- ds:6 — Most active stocks ---
    # Structure: [[item1, item2, ...]] where each item is [stock_arr(27), volume_int]
    ds6 = _parse_af_data(blocks.get("ds:6", ""))
    if ds6 and isinstance(ds6, list):
        items_list = ds6[0] if len(ds6) == 1 and isinstance(_safe(ds6, 0), list) else ds6
        active_list: list[GoogleFinanceStock] = []
        for item in items_list:
            if not isinstance(item, list) or len(item) < 2:
                continue
            # item = [stock_arr(27 elements), volume_int]
            # The stock array has volume appended, so it's 28 elements
            stock_arr = item[:-1] if isinstance(item[-1], (int, float)) and len(item) == 28 else item
            stock = _parse_stock_entry(stock_arr)
            if stock:
                active_list.append(stock)
        if active_list:
            market_trends["most_active"] = active_list

    # --- ds:3 — Gainers and losers ---
    # Structure: [gainers_section, losers_section, trending_section]
    # Each section: [[[stock_arr]], [[stock_arr]], ...] — 6 items per section
    ds3 = _parse_af_data(blocks.get("ds:3", ""))
    if ds3 and isinstance(ds3, list) and len(ds3) >= 2:
        for label, idx in [("gainers", 0), ("losers", 1)]:
            section_data = _safe(ds3, idx)
            if not section_data or not isinstance(section_data, list):
                continue
            items: list[GoogleFinanceStock] = []
            for wrapper in section_data:
                if not isinstance(wrapper, list) or not wrapper:
                    continue
                # wrapper = [[stock_arr]]
                inner = wrapper[0]
                if not isinstance(inner, list) or not inner:
                    continue
                entry = inner[0] if isinstance(inner[0], list) and len(inner[0]) >= 6 else inner
                stock = _parse_stock_entry(entry)
                if stock:
                    items.append(stock)
            if items:
                market_trends[label] = items

    # --- ds:7 — Market news ---
    # Structure: [[news1, news2, ...]] — wrapped in an outer list
    ds7 = _parse_af_data(blocks.get("ds:7", ""))
    if ds7 and isinstance(ds7, list):
        news_list = ds7[0] if len(ds7) == 1 and isinstance(_safe(ds7, 0), list) else ds7
        for item in news_list:
            if not isinstance(item, list):
                continue
            # Each news item: [url, title, source, thumbnail, timestamp, ...]
            if len(item) > 4 and isinstance(_safe(item, 0), str) and _safe(item, 0, "").startswith("http"):
                article = _parse_news_entry(item)
                if article:
                    news.append(article)

    return GoogleFinanceMarketResponse(
        success=True,
        time_taken=0,  # filled by caller
        markets=markets,
        market_trends=market_trends if market_trends else None,
        news=news if news else None,
    )


# ═══════════════════════════════════════════════════════════════════
#  Quote page parser
# ═══════════════════════════════════════════════════════════════════


def _parse_quote(
    blocks: dict[str, str],
    query: str,
) -> GoogleFinanceQuoteResponse:
    """Parse quote page AF blocks into structured response."""
    name = None
    price_str = None
    movement = None
    currency = None
    prev_close_str = None
    after_hours_price = None
    after_hours_movement = None
    similar: list[GoogleFinanceStock] = []
    news: list[GoogleFinanceNewsArticle] = []

    # --- ds:2 or ds:17 — Stock summary ---
    for key in ("ds:2", "ds:17"):
        raw = _parse_af_data(blocks.get(key, ""))
        if not raw or not isinstance(raw, list):
            continue
        # Navigate to the stock array — structure is [[[[stock_arr]]]]
        try:
            stock_arr = raw[0][0][0]
            if isinstance(stock_arr, list) and len(stock_arr) >= 6:
                name = _safe(stock_arr, 2)
                currency = _safe(stock_arr, 4)
                price_data = _safe(stock_arr, 5)
                prev_close = _safe(stock_arr, 7)

                price_val = _safe(price_data, 0) if price_data else None
                change_val = _safe(price_data, 1) if price_data else None
                pct_val = _safe(price_data, 2) if price_data else None

                price_str = _format_price(price_val, currency)
                prev_close_str = _format_price(prev_close, currency) if prev_close else None

                if change_val is not None and pct_val is not None:
                    movement = GoogleFinancePriceMovement(
                        percentage=_format_pct(pct_val),
                        value=_format_change(change_val, currency),
                        movement="up" if change_val > 0 else "down",
                    )

                # After-hours data at index [15] — only for stocks, not crypto/currencies
                ah_data = _safe(stock_arr, 15)
                if (
                    ah_data
                    and isinstance(ah_data, list)
                    and len(ah_data) >= 3
                    and isinstance(_safe(ah_data, 0), (int, float))
                ):
                    ah_price = _safe(ah_data, 0)
                    ah_change = _safe(ah_data, 1)
                    ah_pct = _safe(ah_data, 2)
                    if isinstance(ah_price, (int, float)):
                        after_hours_price = _format_price(ah_price, currency)
                    if (
                        isinstance(ah_change, (int, float))
                        and isinstance(ah_pct, (int, float))
                    ):
                        after_hours_movement = GoogleFinancePriceMovement(
                            percentage=_format_pct(ah_pct),
                            value=_format_change(ah_change, currency),
                            movement="up" if ah_change > 0 else "down",
                        )
                break
        except (IndexError, TypeError):
            continue

    # --- ds:6 — Extended quote (fallback for after-hours) ---
    if not name:
        ds6 = _parse_af_data(blocks.get("ds:6", ""))
        if ds6 and isinstance(ds6, list):
            try:
                # ds:6 structure: [[[mid, null, null, [stock_arr], [null, ticker_pair]]]]
                wrapper = ds6[0][0]
                stock_inner = _safe(wrapper, 3)
                if stock_inner and isinstance(stock_inner, list) and len(stock_inner) >= 6:
                    name = _safe(stock_inner, 2)
                    currency = _safe(stock_inner, 4)
                    price_data = _safe(stock_inner, 5)
                    prev_close = _safe(stock_inner, 7)

                    price_val = _safe(price_data, 0) if price_data else None
                    change_val = _safe(price_data, 1) if price_data else None
                    pct_val = _safe(price_data, 2) if price_data else None

                    price_str = _format_price(price_val, currency)
                    prev_close_str = _format_price(prev_close, currency) if prev_close else None

                    if change_val is not None and pct_val is not None:
                        movement = GoogleFinancePriceMovement(
                            percentage=_format_pct(pct_val),
                            value=_format_change(change_val, currency),
                            movement="up" if change_val > 0 else "down",
                        )

                    # After-hours at index [15]
                    ah_data = _safe(stock_inner, 15)
                    if (
                        ah_data
                        and isinstance(ah_data, list)
                        and len(ah_data) >= 3
                        and isinstance(_safe(ah_data, 0), (int, float))
                    ):
                        ah_price = _safe(ah_data, 0)
                        ah_change = _safe(ah_data, 1)
                        ah_pct = _safe(ah_data, 2)
                        if isinstance(ah_price, (int, float)):
                            after_hours_price = _format_price(ah_price, currency)
                        if (
                            isinstance(ah_change, (int, float))
                            and isinstance(ah_pct, (int, float))
                        ):
                            after_hours_movement = GoogleFinancePriceMovement(
                                percentage=_format_pct(ah_pct),
                                value=_format_change(ah_change, currency),
                                movement="up" if ah_change > 0 else "down",
                            )
            except (IndexError, TypeError):
                pass

    # --- ds:12 — Similar/related stocks ---
    # Structure: [wrapped_list, flat_stock_list]
    # wrapped_list[N] = [[stock_arr]] or [stock_arr]
    # flat_stock_list[N] = stock_arr (27 elements)
    ds12 = _parse_af_data(blocks.get("ds:12", ""))
    if ds12 and isinstance(ds12, list):
        try:
            # Try ds:12[1] first (flat stock arrays)
            for section in ds12:
                if not isinstance(section, list):
                    continue
                for entry in section:
                    if not isinstance(entry, list):
                        continue
                    # Check if this is a stock array (starts with mid string, has 27 elements)
                    if (
                        len(entry) >= 6
                        and isinstance(_safe(entry, 0), str)
                        and _safe(entry, 0, "").startswith("/")
                    ):
                        stock = _parse_stock_entry(entry)
                        if stock and stock.stock != query:
                            similar.append(stock)
                    # Or unwrap [[stock_arr]]
                    elif (
                        len(entry) == 1
                        and isinstance(entry[0], list)
                        and len(entry[0]) >= 6
                    ):
                        stock = _parse_stock_entry(entry[0])
                        if stock and stock.stock != query:
                            similar.append(stock)
        except (IndexError, TypeError):
            pass

    # --- ds:3 — Stock news (on quote page, ds:3 is news not gainers/losers) ---
    for key in ("ds:3", "ds:4"):
        ds_news = _parse_af_data(blocks.get(key, ""))
        if not ds_news or not isinstance(ds_news, list):
            continue
        # On quote pages, ds:3 has format [[category_int, [news_entries...]]]
        # or just a flat list of news entries
        for item in ds_news:
            if not isinstance(item, list):
                continue
            # Check if this looks like a news entry (starts with URL string)
            if len(item) > 4 and isinstance(_safe(item, 0), str) and (
                _safe(item, 0, "").startswith("http")
            ):
                article = _parse_news_entry(item)
                if article:
                    news.append(article)
            # Or it could be wrapped in categories
            elif isinstance(item, list):
                for sub in item:
                    if isinstance(sub, list) and len(sub) > 4 and isinstance(
                        _safe(sub, 0), str
                    ) and _safe(sub, 0, "").startswith("http"):
                        article = _parse_news_entry(sub)
                        if article:
                            news.append(article)

    return GoogleFinanceQuoteResponse(
        success=True,
        time_taken=0,  # filled by caller
        stock=query,
        name=name,
        price=price_str,
        price_movement=movement,
        currency=currency,
        previous_close=prev_close_str,
        after_hours_price=after_hours_price,
        after_hours_movement=after_hours_movement,
        similar_stocks=similar if similar else None,
        news=news if news else None,
    )


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════


async def google_finance_market(
    language: str = "en",
    country: str | None = None,
) -> GoogleFinanceMarketResponse:
    """Fetch Google Finance market overview."""
    cache_key = _cache_key("market", "", language)
    try:
        from app.core.cache import get_cached_response

        cached = await get_cached_response(cache_key)
        if cached:
            logger.info("Finance market cache hit")
            return GoogleFinanceMarketResponse(**cached)
    except Exception:
        pass

    start = time.time()

    params = f"hl={language}"
    if country:
        params += f"&gl={country}"
    url = f"https://www.google.com/finance/?{params}"

    html = await _fetch_html(url)
    if not html:
        return GoogleFinanceMarketResponse(
            success=False,
            time_taken=round(time.time() - start, 3),
            error="Failed to fetch Google Finance page",
        )

    blocks = _extract_af_blocks(html)
    if not blocks:
        return GoogleFinanceMarketResponse(
            success=False,
            time_taken=round(time.time() - start, 3),
            error="No AF_initDataCallback data found in response",
        )

    result = _parse_market_overview(blocks)
    result.time_taken = round(time.time() - start, 3)

    # Cache result
    try:
        from app.core.cache import set_cached_response

        await set_cached_response(cache_key, result.model_dump(), _CACHE_TTL)
    except Exception:
        pass

    return result


async def google_finance_quote(
    query: str,
    language: str = "en",
    country: str | None = None,
) -> GoogleFinanceQuoteResponse:
    """Fetch Google Finance quote for a specific ticker."""
    cache_key = _cache_key("quote", query, language)
    try:
        from app.core.cache import get_cached_response

        cached = await get_cached_response(cache_key)
        if cached:
            logger.info("Finance quote cache hit: %s", query)
            return GoogleFinanceQuoteResponse(**cached)
    except Exception:
        pass

    start = time.time()

    params = f"hl={language}"
    if country:
        params += f"&gl={country}"
    url = f"https://www.google.com/finance/quote/{query}?{params}"

    html = await _fetch_html(url)
    if not html:
        return GoogleFinanceQuoteResponse(
            success=False,
            time_taken=round(time.time() - start, 3),
            stock=query,
            error="Failed to fetch Google Finance quote page",
        )

    # Check if we got a quote page or were redirected to market overview
    if f"/quote/{query}" not in (html[:5000] if len(html) > 5000 else html):
        # Check title
        title_match = re.search(r"<title>([^<]+)</title>", html)
        title = title_match.group(1) if title_match else ""
        if "Stock Price" not in title and query.split(":")[0] not in title:
            return GoogleFinanceQuoteResponse(
                success=False,
                time_taken=round(time.time() - start, 3),
                stock=query,
                error=f"Ticker '{query}' not found. Use format TICKER:EXCHANGE (e.g. AAPL:NASDAQ)",
            )

    blocks = _extract_af_blocks(html)
    if not blocks:
        return GoogleFinanceQuoteResponse(
            success=False,
            time_taken=round(time.time() - start, 3),
            stock=query,
            error="No AF_initDataCallback data found in response",
        )

    result = _parse_quote(blocks, query)
    result.time_taken = round(time.time() - start, 3)

    # Cache result
    try:
        from app.core.cache import set_cached_response

        await set_cached_response(cache_key, result.model_dump(), _CACHE_TTL)
    except Exception:
        pass

    return result
