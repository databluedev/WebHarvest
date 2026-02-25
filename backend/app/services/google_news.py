"""Google News scraper — reverse-engineered AF_initDataCallback parser.

Strategy chain (combined, not pure fallback):
1. nodriver (news.google.com) — PRIMARY: real Chrome loads the SPA,
   we extract the AF_initDataCallback 'ds:2' blob which contains ~100
   articles with direct URLs, timestamps, thumbnails, authors, etc.
2. Google News RSS — SUPPLEMENT: ~100 articles fast (redirect URLs).
3. SearXNG categories=news — VOLUME FILLER: Bing/DDG/Yahoo/Wikinews
   articles if still under the requested count.

All sources combined with URL deduplication. Cached in Redis for 5 min.
"""

import asyncio
import datetime
import hashlib
import json
import logging
import re
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

# SearXNG time_range mapping
_SEARXNG_TIME_RANGE_MAP = {
    "hour": "day",
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}

_GOOGLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

_RESULTS_PER_PAGE = 10  # SearXNG default page size
_MAX_PAGES = 50  # SearXNG safety cap
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
    raw = f"news:{query}|{num}|{lang}|{country or ''}|{time_range or ''}|{sort_by or ''}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:gnews:{h}"


# ===================================================================
# Helper: safe nested list access
# ===================================================================


def _safe_get(data: list | None, *indices, default=None):
    """Safely traverse nested lists by index chain."""
    current = data
    for idx in indices:
        if not isinstance(current, list) or idx >= len(current):
            return default
        current = current[idx]
    return current if current is not None else default


# ===================================================================
# Strategy 1: nodriver — news.google.com AF_initDataCallback parser
# ===================================================================

# AF_initDataCallback field index mapping (reverse-engineered):
#   [2]  = title/headline
#   [4][0] = Unix timestamp (UTC)
#   [6]  = direct article URL (canonical)
#   [8][0][0] = Google News thumbnail proxy path
#   [8][0][13] = original image URL
#   [10][2] = publisher name
#   [10][3][0] = publisher favicon URL
#   [38] = canonical URL (same as [6])
#   [40] = AMP URL (if available)
#   [51] = authors list [[name1], [name2], ...]


def _build_news_google_url(
    query: str,
    lang: str = "en",
    country: str | None = None,
) -> str:
    """Build a news.google.com search URL."""
    gl = (country or "US").upper()
    hl = lang.lower()
    ceid = f"{gl}:{hl}"
    return (
        f"https://news.google.com/search"
        f"?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    )


def _extract_af_init_data(html: str) -> list[dict] | None:
    """Extract AF_initDataCallback blobs from Google News HTML.

    Google News embeds data as:
      AF_initDataCallback({key: 'ds:N', hash: 'M', data:[...]});

    Returns a list of {key, data} dicts for each callback found.
    """
    # Match the exact format: key + hash + data: followed by array
    header_pattern = re.compile(
        r"AF_initDataCallback\(\{key:\s*'([^']+)',\s*hash:\s*'[^']*',\s*data:",
    )

    results = []
    for match in header_pattern.finditer(html):
        key = match.group(1)
        data_start = match.end()  # Position right after "data:"

        # Extract balanced bracket array starting at data_start
        depth = 0
        end = data_start
        for i in range(data_start, min(data_start + 2_000_000, len(html))):
            ch = html[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            if depth == 0 and i > data_start:
                end = i + 1
                break

        data_str = html[data_start:end]

        try:
            parsed = json.loads(data_str)
            results.append({"key": key, "data": parsed})
        except json.JSONDecodeError:
            logger.debug("Failed to parse AF_initDataCallback %s (%d bytes)", key, len(data_str))

    return results if results else None


def _parse_article_entry(entry: list, position: int) -> GoogleNewsArticle | None:
    """Parse a single article data array from ds:2 into GoogleNewsArticle."""
    try:
        title = _safe_get(entry, 2)
        if not title or not isinstance(title, str):
            return None

        # URL — prefer [6], fallback to [38]
        url = _safe_get(entry, 6) or _safe_get(entry, 38)
        if not url or not isinstance(url, str):
            return None

        # Published timestamp
        published_date = None
        date_display = None
        ts = _safe_get(entry, 4, 0)
        if ts and isinstance(ts, (int, float)):
            try:
                dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                published_date = dt.isoformat()
                date_display = dt.strftime("%Y-%m-%d %H:%M UTC")
            except (ValueError, OSError):
                pass

        # Publisher
        source = _safe_get(entry, 10, 2)
        source_url = None
        favicon = _safe_get(entry, 10, 3, 0)
        if favicon and "url=" in favicon:
            # Extract domain from favicon proxy URL
            try:
                fav_parsed = urlparse(favicon)
                for param in fav_parsed.query.split("&"):
                    if param.startswith("url="):
                        source_url = param[4:]
                        break
            except Exception:
                pass
        if not source_url and url:
            parsed = urlparse(url)
            source_url = f"{parsed.scheme}://{parsed.netloc}"

        # Thumbnail — prefer original image [8][0][13], fallback to proxy [8][0][0]
        thumbnail = None
        orig_img = _safe_get(entry, 8, 0, 13)
        if orig_img and isinstance(orig_img, str):
            thumbnail = orig_img
        else:
            proxy_path = _safe_get(entry, 8, 0, 0)
            if proxy_path and isinstance(proxy_path, str):
                thumbnail = f"https://news.google.com{proxy_path}"

        # Snippet — [3] (usually None but check)
        snippet = _safe_get(entry, 3)
        if snippet and not isinstance(snippet, str):
            snippet = None

        return GoogleNewsArticle(
            position=position,
            title=title,
            url=url,
            source=source,
            source_url=source_url,
            date=date_display,
            published_date=published_date,
            snippet=snippet,
            thumbnail=thumbnail,
        )
    except Exception as e:
        logger.debug("Failed to parse article entry at position %d: %s", position, e)
        return None


def _parse_af_articles(af_blobs: list[dict]) -> list[GoogleNewsArticle]:
    """Extract all articles from AF_initDataCallback ds:2 blob.

    Handles both single article entries and cluster/topic groups.

    ds:2 structure:
      ["gsrres", [[entry0, entry1, ...]], "query"]

    Single entry:
      [article_data, None, None, ..., position_index]

    Cluster entry:
      [None, [cluster_title, None, [sub_article, ...], ...]]
    """
    # Find ds:2
    ds2 = None
    for blob in af_blobs:
        if blob["key"] == "ds:2":
            ds2 = blob["data"]
            break

    if ds2 is None:
        # Try any blob that looks like article data (identifier "gsrres")
        for blob in af_blobs:
            data = blob["data"]
            if isinstance(data, list) and len(data) > 1 and data[0] == "gsrres":
                ds2 = data
                break

    if ds2 is None:
        logger.warning("No ds:2 / gsrres blob found in AF_initDataCallback")
        return []

    entries = _safe_get(ds2, 1, 0)
    if not entries or not isinstance(entries, list):
        logger.warning("ds:2[1][0] is empty or not a list")
        return []

    articles: list[GoogleNewsArticle] = []
    position = 1

    for outer in entries:
        if not isinstance(outer, list) or not outer:
            continue

        # --- CLUSTER ENTRY: outer[0] is None, outer[1] has sub-articles ---
        if outer[0] is None and len(outer) > 1 and outer[1] is not None:
            cluster = outer[1]
            sub_articles = _safe_get(cluster, 2)
            if sub_articles and isinstance(sub_articles, list):
                for sub in sub_articles:
                    if isinstance(sub, list):
                        article = _parse_article_entry(sub, position)
                        if article:
                            articles.append(article)
                            position += 1
            continue

        # --- SINGLE ARTICLE ENTRY: outer[0] is the article data ---
        if isinstance(outer[0], list):
            article = _parse_article_entry(outer[0], position)
            if article:
                articles.append(article)
                position += 1

    return articles


async def _fetch_news_google_html(
    url: str,
) -> str | None:
    """Load news.google.com via NoDriverPool and return rendered HTML.

    Scrolls to trigger lazy loading for maximum article count.
    """
    try:
        from app.services.nodriver_helper import NoDriverPool

        pool = NoDriverPool.get()
        tab = await pool.acquire_tab(url)
        if not tab:
            return None

        try:
            # Wait for content to render — Google News uses c-wiz components
            for sel in ["c-wiz article", "article", "main"]:
                try:
                    await tab.select(sel, timeout=8)
                    break
                except Exception:
                    continue

            # Let JS settle
            await tab.sleep(3)

            # Scroll down to trigger lazy loading of more articles
            for _ in range(3):
                await tab.evaluate("window.scrollBy(0, window.innerHeight)")
                await tab.sleep(1.5)

            # Get rendered HTML (contains AF_initDataCallback in <script> tags)
            html = await tab.get_content()
            if not html:
                html = await tab.evaluate("document.documentElement.outerHTML")

            return html
        finally:
            await pool.release_tab(tab)

    except Exception as e:
        logger.warning("nodriver news.google.com fetch failed: %s", e)
        return None


async def _search_via_nodriver(
    query: str,
    num_results: int,
    lang: str,
    country: str | None,
    seen_urls: set[str] | None = None,
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]] | None:
    """PRIMARY strategy: load news.google.com and parse AF_initDataCallback.

    Returns ~100 articles with direct URLs, timestamps, images, publishers.
    """
    if seen_urls is None:
        seen_urls = set()

    url = _build_news_google_url(query, lang, country)
    logger.info("nodriver news.google.com: %s", url)

    html = await _fetch_news_google_html(url)
    if not html:
        logger.warning("nodriver: no HTML from news.google.com")
        return None

    logger.info("nodriver: got %d bytes HTML", len(html))

    # Extract AF_initDataCallback blobs
    af_blobs = _extract_af_init_data(html)
    if not af_blobs:
        logger.warning("nodriver: no AF_initDataCallback found in HTML")
        return None

    logger.info(
        "nodriver: found %d AF_initDataCallback blobs: %s",
        len(af_blobs), [b["key"] for b in af_blobs],
    )

    # Parse articles from ds:2
    articles = _parse_af_articles(af_blobs)
    if not articles:
        logger.warning("nodriver: 0 articles parsed from AF_initDataCallback")
        return None

    # Dedup against seen_urls
    deduped: list[GoogleNewsArticle] = []
    for article in articles:
        normalized = article.url.rstrip("/")
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            deduped.append(article)

    logger.info(
        "nodriver news.google.com: %d articles (%d after dedup)",
        len(articles), len(deduped),
    )

    if not deduped:
        return None

    deduped = deduped[:num_results]
    return deduped, []


# ===================================================================
# Strategy 2: Google News RSS
# ===================================================================


async def _search_via_rss(
    query: str,
    num_results: int,
    lang: str,
    country: str | None,
) -> list[GoogleNewsArticle] | None:
    """Fetch news from Google News RSS feed (~100 articles, fast)."""
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
            headers=_GOOGLE_HEADERS,
        ) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()
            xml_text = resp.text

    except Exception as e:
        logger.warning("Google News RSS fetch failed: %s", e)
        return None

    try:
        articles = _parse_rss_xml(xml_text, num_results)
        if articles:
            logger.info("Google News RSS: %d articles for '%s'", len(articles), query)
            return articles
        logger.warning("Google News RSS: parsed 0 articles")
        return None
    except Exception as e:
        logger.warning("Google News RSS parsing failed: %s", e)
        return None


def _parse_rss_xml(xml_text: str, num_results: int) -> list[GoogleNewsArticle]:
    """Parse Google News RSS XML into article list."""
    root = ET.fromstring(xml_text)

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

        source_el = item.find("source")
        source = source_el.text if source_el is not None else None
        source_url = source_el.get("url") if source_el is not None else None

        description = item.findtext("description", "")
        snippet = _strip_html(description) if description else None

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
                thumbnail=None,
            )
        )

    return articles


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    try:
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "", text).strip()


# ===================================================================
# Strategy 3: SearXNG categories=news (volume filler)
# ===================================================================


async def _fetch_searxng_page(
    base_url: str,
    query: str,
    page: int,
    lang: str,
    time_range: str | None,
) -> list[dict] | None:
    """Fetch a single page of news results from SearXNG (categories=news)."""
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "pageno": page,
        "language": lang,
        "categories": "news",
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
            engines = data.get("unresponsive_engines", [])
            if engines:
                logger.warning("SearXNG: unresponsive engines: %s", engines)
        return results if results else None

    except Exception as e:
        logger.warning("SearXNG news page %d failed: %s", page, e)
        return None


async def _search_via_searxng(
    query: str,
    num_results: int,
    lang: str,
    time_range: str | None,
    seen_urls: set[str] | None = None,
) -> tuple[list[GoogleNewsArticle], list[RelatedSearch]] | None:
    """Fetch news from SearXNG (categories=news) — Bing, DDG, Yahoo, Wikinews."""
    if not settings.SEARXNG_URL:
        return None

    base_url = settings.SEARXNG_URL.rstrip("/")
    pages_needed = min(_MAX_PAGES, ceil(num_results / _RESULTS_PER_PAGE))

    all_articles: list[GoogleNewsArticle] = []
    if seen_urls is None:
        seen_urls = set()

    page_list = list(range(1, pages_needed + 1))

    for batch_start in range(0, len(page_list), _BATCH_SIZE):
        batch = page_list[batch_start : batch_start + _BATCH_SIZE]

        tasks = [
            _fetch_searxng_page(base_url, query, pg, lang, time_range)
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
            "SearXNG batch pages %d-%d: +%d articles (total: %d)",
            batch[0], batch[-1], new_in_batch, len(all_articles),
        )

        if new_in_batch == 0:
            logger.info("SearXNG: no new results in batch, stopping")
            break

        if len(all_articles) >= num_results:
            break

        if batch_start + _BATCH_SIZE < len(page_list):
            await asyncio.sleep(_BATCH_DELAY)

    if not all_articles:
        return None

    all_articles = all_articles[:num_results]
    for i, article in enumerate(all_articles):
        article.position = i + 1

    return all_articles, []


# ===================================================================
# Main entry point
# ===================================================================


async def google_news(
    query: str,
    num_results: int = 100,
    language: str = "en",
    country: str | None = None,
    time_range: str | None = None,
    sort_by: str | None = None,
) -> GoogleNewsResponse:
    """Fetch Google News results — combines ALL sources to maximize results.

    Strategy (combined, not pure fallback):
    1. nodriver (news.google.com) — PRIMARY: AF_initDataCallback parser
       ~100 articles with direct URLs, timestamps, images, publishers
    2. Google News RSS — SUPPLEMENT: ~100 more articles (fast)
    3. SearXNG categories=news — VOLUME: Bing/DDG/Yahoo/Wikinews

    All sources COMBINED with URL deduplication.
    Results cached in Redis for 5 minutes.
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
            logger.info("News cache hit for '%s'", query)
            return GoogleNewsResponse(**data)
    except Exception:
        pass

    articles: list[GoogleNewsArticle] = []
    related: list[RelatedSearch] = []
    seen_urls: set[str] = set()
    strategies_used: list[str] = []

    # ── Strategy 1: nodriver — news.google.com (PRIMARY) ──
    nd_result = await _search_via_nodriver(
        query, num_results, language, country, seen_urls=seen_urls,
    )
    if nd_result is not None:
        nd_articles, nd_related = nd_result
        articles.extend(nd_articles)
        if nd_related:
            related = nd_related
        if nd_articles:
            strategies_used.append("nodriver")
            logger.info(
                "Google News nodriver: %d articles for '%s'",
                len(nd_articles), query,
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

    # ── Strategy 3: SearXNG categories=news (volume filler) ──
    if len(articles) < num_results:
        remaining = num_results - len(articles)
        searxng_result = await _search_via_searxng(
            query, remaining, language, time_range, seen_urls=seen_urls,
        )
        if searxng_result is not None:
            sx_articles, sx_related = searxng_result
            articles.extend(sx_articles)
            if sx_related and not related:
                related = sx_related
            if sx_articles:
                strategies_used.append("searxng")
                logger.info(
                    "Google News SearXNG: +%d articles (total: %d) for '%s'",
                    len(sx_articles), len(articles), query,
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
