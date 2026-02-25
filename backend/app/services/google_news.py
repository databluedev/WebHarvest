"""Google News scraper — fetches and parses Google News results.

Strategy chain:
1. SearXNG (categories=news, parallel pagination in batches of 5)
2. Google News RSS (news.google.com/rss/search, parsed with xml.etree)
3. Direct Google scrape (tbm=nws, curl_cffi/httpx + BS4)

No browser needed — pure HTTP, fast, multi-user safe.
Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import json
import logging
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from math import ceil
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.schemas.data_google import (
    GoogleNewsArticle,
    GoogleNewsResponse,
    RelatedSearch,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes

# SearXNG time_range mapping (SearXNG only supports day/week/month/year)
_SEARXNG_TIME_RANGE_MAP = {
    "hour": "day",
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}

# Google direct scrape time range (tbs parameter)
_GOOGLE_TIME_RANGE_MAP = {
    "hour": "qdr:h",
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "year": "qdr:y",
}

# Google direct scrape sort parameter
_GOOGLE_SORT_MAP = {
    "date": "sbd:1",
    "relevance": None,
}

# Desktop Chrome User-Agent
_GOOGLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
}

_RESULTS_PER_PAGE = 10  # SearXNG default page size
_MAX_PAGES = 50  # Safety cap
_BATCH_SIZE = 5  # Parallel pages per batch
_BATCH_DELAY = 0.5  # Seconds between batches


def _cache_key(
    query: str,
    num: int,
    lang: str,
    country: str | None,
    time_range: str | None,
    sort_by: str | None,
) -> str:
    """Build a deterministic Redis cache key for news results."""
    raw = f"news:{query}|{num}|{lang}|{country or ''}|{time_range or ''}|{sort_by or ''}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:gnews:{h}"


# ===================================================================
# Strategy 1: SearXNG (categories=news, parallel pagination)
# ===================================================================


async def _fetch_searxng_page(
    base_url: str,
    query: str,
    page: int,
    lang: str,
    time_range: str | None,
    sort_by: str | None,
) -> list[dict] | None:
    """Fetch a single page of news results from SearXNG."""
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "engines": "google news",
        "pageno": page,
        "language": lang,
    }
    if time_range and time_range in _SEARXNG_TIME_RANGE_MAP:
        params["time_range"] = _SEARXNG_TIME_RANGE_MAP[time_range]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results and page == 1:
            # Debug: log why SearXNG returned empty
            engines = data.get("unresponsive_engines", [])
            if engines:
                logger.warning("SearXNG: unresponsive engines: %s", engines)
            logger.debug(
                "SearXNG news page 1 empty — keys: %s, engines: %s",
                list(data.keys()), data.get("unresponsive_engines"),
            )
        return results if results else None

    except Exception as e:
        logger.warning(f"SearXNG news page {page} failed: {e}")
        return None


async def _search_via_searxng(
    query: str,
    num_results: int,
    lang: str,
    time_range: str | None,
    sort_by: str | None,
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]] | None:
    """Fetch news results from SearXNG with parallel pagination."""
    if not settings.SEARXNG_URL:
        return None

    base_url = settings.SEARXNG_URL.rstrip("/")

    pages_needed = min(_MAX_PAGES, ceil(num_results / _RESULTS_PER_PAGE))

    all_articles: list[GoogleNewsArticle] = []
    seen_urls: set[str] = set()
    related: list[RelatedSearch] = []

    page_list = list(range(1, pages_needed + 1))

    for batch_start in range(0, len(page_list), _BATCH_SIZE):
        batch = page_list[batch_start : batch_start + _BATCH_SIZE]

        tasks = [
            _fetch_searxng_page(base_url, query, pg, lang, time_range, sort_by)
            for pg in batch
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        new_in_batch = 0
        for page_results in batch_results:
            if isinstance(page_results, Exception) or page_results is None:
                continue

            for item in page_results:
                url = item.get("url", "")
                normalized_url = url.rstrip("/")
                if not url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)

                # Extract source from engine or URL domain
                source = item.get("engine")
                source_url = None
                if url:
                    parsed = urlparse(url)
                    source_url = f"{parsed.scheme}://{parsed.netloc}"
                    if not source:
                        source = parsed.netloc.replace("www.", "")

                article = GoogleNewsArticle(
                    position=len(all_articles) + 1,
                    title=item.get("title", ""),
                    url=url,
                    source=source,
                    source_url=source_url,
                    date=None,
                    published_date=item.get("publishedDate"),
                    snippet=item.get("content"),
                    thumbnail=item.get("img_src"),
                )
                all_articles.append(article)
                new_in_batch += 1

        logger.info(
            f"SearXNG news batch pages {batch[0]}-{batch[-1]}: "
            f"+{new_in_batch} articles (total: {len(all_articles)})"
        )

        # Stop early if batch returned no new results
        if new_in_batch == 0:
            logger.info("SearXNG news: no new results in batch, stopping pagination")
            break

        # Have enough?
        if len(all_articles) >= num_results:
            break

        # Delay between batches
        if batch_start + _BATCH_SIZE < len(page_list):
            await asyncio.sleep(_BATCH_DELAY)

    if not all_articles:
        return None

    # Trim to requested count
    all_articles = all_articles[:num_results]

    # Re-number positions
    for i, article in enumerate(all_articles):
        article.position = i + 1

    return all_articles, related


# ===================================================================
# Strategy 2: Google News RSS
# ===================================================================


async def _search_via_rss(
    query: str,
    num_results: int,
    lang: str,
    country: str | None,
) -> list[GoogleNewsArticle] | None:
    """Fetch news from Google News RSS feed."""
    gl = (country or "US").upper()
    hl = lang.lower()
    ceid = f"{gl}:{hl}"

    rss_url = (
        f"https://news.google.com/rss/search"
        f"?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    )

    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": _GOOGLE_HEADERS["User-Agent"],
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        ) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()
            xml_text = resp.text

    except Exception as e:
        logger.warning(f"Google News RSS fetch failed: {e}")
        return None

    try:
        articles = _parse_rss_xml(xml_text, num_results)
        if articles:
            logger.info(f"Google News RSS: {len(articles)} articles for '{query}'")
            return articles
        logger.warning("Google News RSS: parsed 0 articles")
        return None
    except Exception as e:
        logger.warning(f"Google News RSS parsing failed: {e}")
        return None


def _parse_rss_xml(xml_text: str, num_results: int) -> list[GoogleNewsArticle]:
    """Parse Google News RSS XML into article list."""
    root = ET.fromstring(xml_text)

    # RSS 2.0 structure: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel")
    if channel is None:
        return []

    articles: list[GoogleNewsArticle] = []

    for i, item in enumerate(channel.findall("item")):
        if len(articles) >= num_results:
            break

        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate")

        # Source from <source> tag
        source_el = item.find("source")
        source = source_el.text if source_el is not None else None
        source_url = source_el.get("url") if source_el is not None else None

        # Description (snippet) — may contain HTML
        description = item.findtext("description", "")
        snippet = _strip_html(description) if description else None

        # Parse pubDate to ISO format
        published_date = None
        date_display = None
        if pub_date:
            try:
                dt = parsedate_to_datetime(pub_date)
                published_date = dt.isoformat()
                date_display = pub_date
            except Exception:
                date_display = pub_date

        articles.append(
            GoogleNewsArticle(
                position=i + 1,
                title=title,
                url=link,
                source=source,
                source_url=source_url,
                date=date_display,
                published_date=published_date,
                snippet=snippet,
                thumbnail=None,  # RSS doesn't include thumbnails
            )
        )

    return articles


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    try:
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        # Fallback: basic tag stripping
        import re

        return re.sub(r"<[^>]+>", "", text).strip()


# ===================================================================
# Strategy 3: Direct Google scrape (tbm=nws)
# ===================================================================


def _build_google_news_url(
    query: str,
    num: int = 100,
    lang: str = "en",
    country: str | None = None,
    time_range: str | None = None,
    sort_by: str | None = None,
    start: int = 0,
) -> str:
    """Build a Google News search URL."""
    params = [
        f"q={quote_plus(query)}",
        f"tbm=nws",
        f"num={min(num, 100)}",
        f"hl={lang}",
    ]
    if start > 0:
        params.append(f"start={start}")
    if country:
        params.append(f"gl={country}")
    if time_range and time_range in _GOOGLE_TIME_RANGE_MAP:
        tbs = _GOOGLE_TIME_RANGE_MAP[time_range]
        # Combine with sort if needed
        if sort_by and sort_by in _GOOGLE_SORT_MAP and _GOOGLE_SORT_MAP[sort_by]:
            tbs = f"{tbs},{_GOOGLE_SORT_MAP[sort_by]}"
        params.append(f"tbs={tbs}")
    elif sort_by and sort_by in _GOOGLE_SORT_MAP and _GOOGLE_SORT_MAP[sort_by]:
        params.append(f"tbs={_GOOGLE_SORT_MAP[sort_by]}")

    return f"https://www.google.com/search?{'&'.join(params)}"


def _get_proxy_url() -> str | None:
    """Get proxy URL from BUILTIN_PROXY_URL for direct scrape requests."""
    try:
        from app.config import settings

        raw = settings.BUILTIN_PROXY_URL
        if not raw:
            return None
        first = raw.split(",")[0].strip()
        return first if first else None
    except Exception:
        return None


def _is_blocked_page(html: str) -> bool:
    """Check if Google returned a JS-required redirect or consent page."""
    lower = html.lower()
    if "captcha" in lower or "unusual traffic" in lower:
        return True
    # JS-required redirect page (no actual results)
    if "please click here if you are not redirected" in lower:
        return True
    return False


async def _fetch_google_html(url: str) -> str | None:
    """Fetch Google News HTML using curl_cffi with proxy support.

    Uses BUILTIN_PROXY_URL if configured (rotating residential proxy).
    Falls back to direct request if no proxy.
    """
    proxy_url = _get_proxy_url()
    if not proxy_url:
        logger.warning(
            "Google News direct scrape: no BUILTIN_PROXY_URL configured — "
            "Google will likely block server IP"
        )

    # Try curl_cffi (best TLS fingerprint)
    try:
        from curl_cffi.requests import AsyncSession

        kwargs: dict = {
            "headers": _GOOGLE_HEADERS,
            "timeout": 20,
            "allow_redirects": True,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url

        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(url, **kwargs)
            if resp.status_code == 200:
                if not _is_blocked_page(resp.text):
                    return resp.text
                logger.warning("Google News: blocked page via curl_cffi")
            else:
                logger.warning(f"Google News returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"curl_cffi Google News fetch failed: {e}")

    # Fallback to httpx (with proxy if available)
    try:
        client_kwargs: dict = {
            "timeout": 20,
            "follow_redirects": True,
            "headers": _GOOGLE_HEADERS,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                if not _is_blocked_page(resp.text):
                    return resp.text
                logger.warning("Google News: blocked page via httpx")
    except Exception as e:
        logger.warning(f"httpx Google News fetch failed: {e}")

    return None


def _parse_google_news_html(
    html: str, query: str, offset: int = 0
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]]:
    """Parse Google News SERP HTML into structured data."""
    soup = BeautifulSoup(html, "lxml")

    articles = _parse_news_cards(soup, offset)
    related = _parse_related_searches(soup)

    return articles, related


def _parse_news_cards(
    soup: BeautifulSoup, offset: int = 0
) -> list[GoogleNewsArticle]:
    """Extract news article cards from Google News SERP."""
    results: list[GoogleNewsArticle] = []

    # Primary selector: div.SoaBEf (standard news card container)
    containers = soup.select("div.SoaBEf")

    # Fallback: data-news-doc-id attribute
    if not containers:
        containers = soup.select("div[data-news-doc-id]")

    # Fallback: generic news result blocks
    if not containers:
        containers = soup.select("div.dbsr, div.WlydOe, g-card")

    for i, container in enumerate(containers):
        try:
            # Title
            title = None
            for sel in ["div.mCBkyc", "div.n0jPhd", "div.JheGif", "a div[role='heading']"]:
                title_el = container.select_one(sel)
                if title_el:
                    title = title_el.get_text(strip=True)
                    break

            if not title:
                # Try any link with substantial text
                link_el = container.select_one("a")
                if link_el:
                    title = link_el.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

            # URL — from <a> href
            url = ""
            for a_el in container.select("a[href]"):
                href = a_el.get("href", "")
                if href and not href.startswith("#") and not href.startswith("/search"):
                    if "/url?q=" in href:
                        url = href.split("/url?q=")[1].split("&")[0]
                    else:
                        url = href
                    break

            if not url:
                continue

            # Source (news outlet)
            source = None
            for sel in ["div.CEMjEf span", "span.CEMjEf", "div.XTjFC", "span.WF4CUc"]:
                source_el = container.select_one(sel)
                if source_el:
                    source = source_el.get_text(strip=True)
                    break

            # Source URL from domain
            source_url = None
            if url:
                parsed = urlparse(url)
                source_url = f"{parsed.scheme}://{parsed.netloc}"
                if not source:
                    source = parsed.netloc.replace("www.", "")

            # Date
            date = None
            for sel in ["div.OSrXXb span", "span.WG9SHc", "span.r0bn4c", "span.ZE0LJd"]:
                date_el = container.select_one(sel)
                if date_el:
                    date = date_el.get_text(strip=True)
                    break

            # Snippet
            snippet = None
            for sel in ["div.GI74Re", "div.Y3v8qd", "div.s3v9rd"]:
                snippet_el = container.select_one(sel)
                if snippet_el:
                    snippet = snippet_el.get_text(separator=" ", strip=True)
                    break

            # Thumbnail
            thumbnail = None
            img_el = container.select_one("img[src]")
            if img_el:
                src = img_el.get("src", "")
                if src and not src.startswith("data:"):
                    thumbnail = src

            results.append(
                GoogleNewsArticle(
                    position=offset + i + 1,
                    title=title,
                    url=url,
                    source=source,
                    source_url=source_url,
                    date=date,
                    published_date=None,
                    snippet=snippet,
                    thumbnail=thumbnail,
                )
            )
        except Exception as e:
            logger.debug(f"Failed to parse news card {i}: {e}")
            continue

    return results


def _parse_related_searches(soup: BeautifulSoup) -> list[RelatedSearch]:
    """Extract related searches from Google News SERP."""
    related: list[RelatedSearch] = []
    seen: set[str] = set()

    for sel in [
        "div#botstuff a",
        "a.k8XOCe",
        "div.s75CSd a",
        "a.EIaa9b",
    ]:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            href = el.get("href", "")
            if (
                text
                and len(text) > 2
                and len(text) < 100
                and text.lower() not in seen
                and ("/search?" in href or not href)
            ):
                seen.add(text.lower())
                related.append(RelatedSearch(query=text))

    return related


_SCRAPE_PAGE_SIZE = 10  # Google News tbm=nws returns ~10 per page
_SCRAPE_MAX_PAGES = 50  # Safety cap for direct scrape pagination
_SCRAPE_BATCH_SIZE = 3  # Parallel pages per batch
_SCRAPE_BATCH_DELAY = 1.0  # Seconds between batches (be gentle with Google)


async def _fetch_scrape_page(
    query: str,
    lang: str,
    country: str | None,
    time_range: str | None,
    sort_by: str | None,
    start: int,
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]] | None:
    """Fetch a single page of direct Google News scrape results."""
    url = _build_google_news_url(
        query,
        num=_SCRAPE_PAGE_SIZE,
        lang=lang,
        country=country,
        time_range=time_range,
        sort_by=sort_by,
        start=start,
    )

    html = await _fetch_google_html(url)
    if not html:
        return None

    html_lower = html.lower()
    if "captcha" in html_lower or "unusual traffic" in html_lower:
        logger.warning("Google CAPTCHA detected during news direct scrape (start=%d)", start)
        return None

    try:
        articles, related = _parse_google_news_html(html, query, offset=start)
        if articles:
            return articles, related
    except Exception as e:
        logger.warning(f"Google News HTML parsing failed (start={start}): {e}")

    return None


async def _search_via_direct_scrape(
    query: str,
    num_results: int,
    lang: str,
    country: str | None,
    time_range: str | None,
    sort_by: str | None,
    seen_urls: set[str] | None = None,
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]] | None:
    """Fetch Google News via tbm=nws with paginated scraping.

    Paginates with start=0,10,20... in parallel batches of 3.
    Deduplicates against seen_urls (from RSS or other sources).
    """
    if seen_urls is None:
        seen_urls = set()

    pages_needed = min(_SCRAPE_MAX_PAGES, ceil(num_results / _SCRAPE_PAGE_SIZE))

    all_articles: list[GoogleNewsArticle] = []
    all_related: list[RelatedSearch] = []

    start_offsets = [i * _SCRAPE_PAGE_SIZE for i in range(pages_needed)]

    for batch_start in range(0, len(start_offsets), _SCRAPE_BATCH_SIZE):
        batch = start_offsets[batch_start : batch_start + _SCRAPE_BATCH_SIZE]

        tasks = [
            _fetch_scrape_page(query, lang, country, time_range, sort_by, offset)
            for offset in batch
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        new_in_batch = 0
        for page_result in batch_results:
            if isinstance(page_result, Exception) or page_result is None:
                continue

            articles, related = page_result
            if not all_related and related:
                all_related = related

            for article in articles:
                normalized = article.url.rstrip("/")
                if normalized in seen_urls:
                    continue
                seen_urls.add(normalized)
                all_articles.append(article)
                new_in_batch += 1

        logger.info(
            "Direct scrape batch start=%d-%d: +%d articles (total: %d)",
            batch[0], batch[-1], new_in_batch, len(all_articles),
        )

        # Stop early if batch returned no new results (hit end of Google results)
        if new_in_batch == 0:
            logger.info("Direct scrape: no new results in batch, stopping")
            break

        # Have enough?
        if len(all_articles) >= num_results:
            break

        # Delay between batches
        if batch_start + _SCRAPE_BATCH_SIZE < len(start_offsets):
            await asyncio.sleep(_SCRAPE_BATCH_DELAY)

    if not all_articles:
        return None

    all_articles = all_articles[:num_results]
    return all_articles, all_related


# ===================================================================
# Main entry point
# ===================================================================


async def google_news(
    query: str,
    num_results: int = 100,
    language: str = "en",
    country: str | None = None,
    time_range: str | None = None,  # hour, day, week, month, year
    sort_by: str | None = None,  # relevance, date
) -> GoogleNewsResponse:
    """Fetch Google News results — combines sources to maximize results.

    Strategy:
    1. SearXNG (engines=google news, parallel pagination) — if configured
    2. Google News RSS (~100 articles, fast)
    3. Direct Google scrape (tbm=nws, paginated) — fills remaining quota

    RSS + direct scrape are COMBINED (not pure fallback) to exceed the
    ~100 RSS cap. Deduplication by URL across all sources.
    Results are cached in Redis for 5 minutes.
    """
    start = time.time()

    # Check Redis cache
    key = _cache_key(query, num_results, language, country, time_range, sort_by)
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - start, 3)
            logger.info(f"News cache hit for '{query}'")
            return GoogleNewsResponse(**data)
    except Exception:
        pass

    articles: list[GoogleNewsArticle] = []
    related: list[RelatedSearch] = []
    seen_urls: set[str] = set()
    strategies_used: list[str] = []

    # ── Strategy 1: SearXNG ──
    searxng_result = await _search_via_searxng(
        query, num_results, language, time_range, sort_by
    )
    if searxng_result is not None:
        searxng_articles, searxng_related = searxng_result
        for a in searxng_articles:
            normalized = a.url.rstrip("/")
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                articles.append(a)
        if searxng_related:
            related = searxng_related
        if searxng_articles:
            strategies_used.append("searxng")
            logger.info(
                "Google News SearXNG: %d articles for '%s'",
                len(searxng_articles), query,
            )

    # ── Strategy 2: Google News RSS (~100 articles, fast) ──
    if len(articles) < num_results:
        rss_articles = await _search_via_rss(query, num_results, language, country)
        if rss_articles:
            added = 0
            for a in rss_articles:
                normalized = a.url.rstrip("/")
                if normalized not in seen_urls:
                    seen_urls.add(normalized)
                    articles.append(a)
                    added += 1
            if added:
                strategies_used.append("rss")
                logger.info(
                    "Google News RSS: +%d new articles (total: %d) for '%s'",
                    added, len(articles), query,
                )

    # ── Strategy 3: Direct Google scrape (paginated, fills remaining) ──
    if len(articles) < num_results:
        remaining = num_results - len(articles)
        scrape_result = await _search_via_direct_scrape(
            query, remaining, language, country, time_range, sort_by,
            seen_urls=seen_urls,
        )
        if scrape_result is not None:
            scrape_articles, scrape_related = scrape_result
            articles.extend(scrape_articles)
            if scrape_related and not related:
                related = scrape_related
            if scrape_articles:
                strategies_used.append("direct_scrape")
                logger.info(
                    "Google News direct scrape: +%d articles (total: %d) for '%s'",
                    len(scrape_articles), len(articles), query,
                )

    elapsed = round(time.time() - start, 3)

    if not articles:
        return GoogleNewsResponse(
            success=False,
            query=query,
            time_taken=elapsed,
            source_strategy="none",
        )

    # Trim to requested count and re-number
    articles = articles[:num_results]
    for i, article in enumerate(articles):
        article.position = i + 1

    source_strategy = "+".join(strategies_used) if strategies_used else "none"

    result = GoogleNewsResponse(
        query=query,
        total_results=str(len(articles)),
        time_taken=elapsed,
        source_strategy=source_strategy,
        articles=articles,
        related_searches=related,
    )

    # Cache in Redis
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
