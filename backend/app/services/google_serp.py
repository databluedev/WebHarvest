"""Google SERP scraper — fetches and parses Google search results.

Strategy chain:
1. SearXNG (fast JSON API, no browser needed)
2. Direct Google scrape (curl_cffi with stealth headers + BS4 parser)
3. googlesearch library (basic fallback)

Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.schemas.data_google import (
    FeaturedSnippet,
    GoogleOrganicResult,
    GoogleSearchResponse,
    KnowledgePanel,
    PeopleAlsoAsk,
    RelatedSearch,
    Sitelink,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes

# Time range mapping for Google's qdr parameter
_TIME_RANGE_MAP = {
    "hour": "qdr:h",
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "year": "qdr:y",
}


def _cache_key(
    query: str,
    num: int,
    page: int,
    lang: str,
    country: str | None,
    time_range: str | None,
) -> str:
    """Build a deterministic Redis cache key for SERP results."""
    raw = f"{query}|{num}|{page}|{lang}|{country or ''}|{time_range or ''}"
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:google:{h}"


def _build_google_url(
    query: str,
    num: int = 10,
    page: int = 1,
    lang: str = "en",
    country: str | None = None,
    safe: bool = False,
    time_range: str | None = None,
) -> str:
    """Build a Google search URL with parameters."""
    params = [
        f"q={quote_plus(query)}",
        f"num={num}",
        f"hl={lang}",
    ]
    if page > 1:
        params.append(f"start={(page - 1) * num}")
    if country:
        params.append(f"gl={country}")
    if safe:
        params.append("safe=active")
    if time_range and time_range in _TIME_RANGE_MAP:
        params.append(f"tbs={_TIME_RANGE_MAP[time_range]}")

    return f"https://www.google.com/search?{'&'.join(params)}"


# ═══════════════════════════════════════════════════════════════════
# Strategy 1: SearXNG
# ═══════════════════════════════════════════════════════════════════


async def _search_via_searxng(
    query: str,
    num: int,
    page: int,
    lang: str,
    time_range: str | None,
) -> GoogleSearchResponse | None:
    """Fetch results from self-hosted SearXNG (Google backend)."""
    if not settings.SEARXNG_URL:
        return None

    base_url = settings.SEARXNG_URL.rstrip("/")
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "engines": "google",
        "pageno": page,
        "language": lang,
    }
    if time_range and time_range in _TIME_RANGE_MAP:
        params["time_range"] = time_range

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        organic = []
        for i, item in enumerate(data.get("results", [])[:num]):
            organic.append(
                GoogleOrganicResult(
                    position=i + 1 + ((page - 1) * num),
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    displayed_url=urlparse(item.get("url", "")).netloc,
                    snippet=item.get("content", ""),
                )
            )

        # SearXNG also returns some extra data
        related = []
        for s in data.get("suggestions", []):
            related.append(RelatedSearch(query=s))

        info_boxes = data.get("infoboxes", [])
        knowledge = None
        if info_boxes:
            box = info_boxes[0]
            knowledge = KnowledgePanel(
                title=box.get("infobox", ""),
                description=box.get("content", ""),
                source=box.get("engine", ""),
            )

        return GoogleSearchResponse(
            query=query,
            time_taken=0,  # Will be set by caller
            organic_results=organic,
            related_searches=related,
            knowledge_panel=knowledge,
        )

    except Exception as e:
        logger.warning(f"SearXNG Google search failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# Strategy 2: Direct Google scrape + BS4 parser
# ═══════════════════════════════════════════════════════════════════

# Desktop Chrome User-Agent for Google
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


async def _fetch_google_html(url: str) -> str | None:
    """Fetch Google SERP HTML using curl_cffi (best TLS fingerprint)."""
    try:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                headers=_GOOGLE_HEADERS,
                timeout=15,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"Google returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"curl_cffi Google fetch failed: {e}")

    # Fallback to httpx
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=_GOOGLE_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning(f"httpx Google fetch failed: {e}")

    return None


def _parse_google_html(html: str, query: str, page: int, num: int) -> GoogleSearchResponse:
    """Parse Google SERP HTML into structured data using BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")

    organic_results = _parse_organic_results(soup, page, num)
    featured_snippet = _parse_featured_snippet(soup)
    people_also_ask = _parse_people_also_ask(soup)
    related_searches = _parse_related_searches(soup)
    knowledge_panel = _parse_knowledge_panel(soup)
    total_results = _parse_total_results(soup)

    return GoogleSearchResponse(
        query=query,
        total_results=total_results,
        time_taken=0,  # Set by caller
        organic_results=organic_results,
        featured_snippet=featured_snippet,
        people_also_ask=people_also_ask,
        related_searches=related_searches,
        knowledge_panel=knowledge_panel,
    )


def _parse_organic_results(
    soup: BeautifulSoup, page: int, num: int
) -> list[GoogleOrganicResult]:
    """Extract organic search results from Google SERP."""
    results = []
    offset = (page - 1) * num

    # Primary: div.g containers (standard Google results)
    containers = soup.select("div.g")

    # Fallback: data-sokoban-container divs
    if not containers:
        containers = soup.select("div[data-sokoban-container]")

    # Fallback: tF2Cxc class (another Google result wrapper)
    if not containers:
        containers = soup.select("div.tF2Cxc")

    for i, container in enumerate(containers):
        try:
            # Title — h3 tag
            title_el = container.select_one("h3")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # URL — first <a> with href
            link_el = container.select_one("a[href]")
            if not link_el:
                continue
            url = link_el.get("href", "")
            # Skip Google internal links
            if not url or url.startswith("/search") or url.startswith("#"):
                continue
            # Handle Google redirect URLs
            if "/url?q=" in url:
                url = url.split("/url?q=")[1].split("&")[0]

            # Displayed URL — cite element
            displayed_url = None
            cite_el = container.select_one("cite")
            if cite_el:
                displayed_url = cite_el.get_text(strip=True)

            # Snippet — multiple possible selectors
            snippet = None
            for sel in [
                "div[data-sncf]",
                "div.VwiC3b",
                "span.aCOpRe",
                "div.IsZvec",
                "div[style='-webkit-line-clamp:2']",
            ]:
                snippet_el = container.select_one(sel)
                if snippet_el:
                    snippet = snippet_el.get_text(separator=" ", strip=True)
                    break

            # If no snippet found, try any <span> or <div> with enough text
            if not snippet:
                for el in container.select("span, div"):
                    text = el.get_text(strip=True)
                    if len(text) > 50 and text != title:
                        snippet = text
                        break

            # Date — look for date patterns
            date = None
            for sel in ["span.LEwnzc", "span.MUxGbd", "span.f"]:
                date_el = container.select_one(sel)
                if date_el:
                    date_text = date_el.get_text(strip=True)
                    # Simple date pattern check
                    if re.search(r"\d{4}|\w{3}\s+\d{1,2}", date_text):
                        date = date_text
                        break

            # Sitelinks
            sitelinks = _parse_sitelinks(container)

            results.append(
                GoogleOrganicResult(
                    position=offset + i + 1,
                    title=title,
                    url=url,
                    displayed_url=displayed_url,
                    snippet=snippet,
                    date=date,
                    sitelinks=sitelinks if sitelinks else None,
                )
            )
        except Exception as e:
            logger.debug(f"Failed to parse organic result {i}: {e}")
            continue

    return results


def _parse_sitelinks(container) -> list[Sitelink]:
    """Extract sitelinks from a search result container."""
    sitelinks = []
    # Inline sitelinks
    for sl in container.select("a.fl, table.jmjoTe a, div.HiHjCd a"):
        sl_title = sl.get_text(strip=True)
        sl_url = sl.get("href", "")
        if sl_title and sl_url and not sl_url.startswith("#"):
            sitelinks.append(Sitelink(title=sl_title, url=sl_url))
    return sitelinks


def _parse_featured_snippet(soup: BeautifulSoup) -> FeaturedSnippet | None:
    """Extract featured snippet (position 0) from Google SERP."""
    # Multiple selectors for featured snippet containers
    for sel in [
        "div.xpdopen",
        "div[data-tts='answers']",
        "div.IZ6rdc",
        "block-component[data-bm]",
    ]:
        container = soup.select_one(sel)
        if not container:
            continue

        # Get the answer content
        content = None
        for content_sel in ["span.hgKElc", "div.IZx3Hd", "div.LGOjhe"]:
            content_el = container.select_one(content_sel)
            if content_el:
                content = content_el.get_text(separator=" ", strip=True)
                break

        if not content:
            continue

        # Get title and URL
        title = ""
        url = ""
        title_el = container.select_one("h3")
        if title_el:
            title = title_el.get_text(strip=True)
        link_el = container.select_one("a[href]")
        if link_el:
            url = link_el.get("href", "")

        # Determine type
        snippet_type = "paragraph"
        if container.select("ol, ul"):
            snippet_type = "list"
        elif container.select("table"):
            snippet_type = "table"

        return FeaturedSnippet(
            title=title,
            url=url,
            content=content,
            type=snippet_type,
        )

    return None


def _parse_people_also_ask(soup: BeautifulSoup) -> list[PeopleAlsoAsk]:
    """Extract 'People Also Ask' questions from Google SERP."""
    questions = []

    # Primary selector
    for el in soup.select("div.related-question-pair, div[data-q]"):
        q = el.get("data-q", "")
        if not q:
            # Try extracting from text content
            span = el.select_one("span")
            if span:
                q = span.get_text(strip=True)
        if q:
            # Try to get the answer snippet
            snippet = None
            answer_el = el.select_one("div.wDYxhc, div[data-attrid]")
            if answer_el:
                snippet = answer_el.get_text(separator=" ", strip=True)[:300]
            questions.append(PeopleAlsoAsk(question=q, snippet=snippet))

    # Fallback: aria-expanded elements
    if not questions:
        for el in soup.select("[aria-expanded]"):
            text = el.get_text(strip=True)
            if text and "?" in text and len(text) < 200:
                questions.append(PeopleAlsoAsk(question=text))

    return questions


def _parse_related_searches(soup: BeautifulSoup) -> list[RelatedSearch]:
    """Extract related searches from bottom of Google SERP."""
    related = []
    seen = set()

    # Primary: bottom related searches
    for sel in [
        "div#botstuff a",
        "a.k8XOCe",
        "div.s75CSd a",
        "a.EIaa9b",
    ]:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            href = el.get("href", "")
            # Filter: must look like a search query link
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


def _parse_knowledge_panel(soup: BeautifulSoup) -> KnowledgePanel | None:
    """Extract knowledge panel from Google SERP."""
    # Knowledge panel container
    kp = soup.select_one("div.kp-wholepage, div.knowledge-panel, div.osrp-blk")
    if not kp:
        return None

    # Title
    title = ""
    for sel in ["h2[data-attrid='title']", "div[data-attrid='title'] span", "h2.qrShPb"]:
        el = kp.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            break

    if not title:
        return None

    # Type (subtitle)
    type_str = None
    for sel in ["div[data-attrid='subtitle']", "div.wwUB2c"]:
        el = kp.select_one(sel)
        if el:
            type_str = el.get_text(strip=True)
            break

    # Description
    description = None
    for sel in ["div.kno-rdesc span", "span.LrzXr", "div[data-attrid='description'] span"]:
        el = kp.select_one(sel)
        if el:
            description = el.get_text(strip=True)
            break

    # Source
    source = None
    source_el = kp.select_one("a.ruhjFe, span.Yy0acb")
    if source_el:
        source = source_el.get_text(strip=True)

    # Image
    image_url = None
    img_el = kp.select_one("img.rISBZc, g-img img")
    if img_el:
        image_url = img_el.get("src") or img_el.get("data-src")

    # Attributes (key-value pairs)
    attributes = {}
    for attr_div in kp.select("div[data-attrid]"):
        attrid = attr_div.get("data-attrid", "")
        if attrid in ("title", "subtitle", "description"):
            continue
        spans = attr_div.select("span")
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True).rstrip(":")
            val = spans[-1].get_text(strip=True)
            if key and val and key != val:
                attributes[key] = val

    return KnowledgePanel(
        title=title,
        type=type_str,
        description=description,
        source=source,
        image_url=image_url,
        attributes=attributes if attributes else None,
    )


def _parse_total_results(soup: BeautifulSoup) -> str | None:
    """Extract 'About X results' text."""
    stats = soup.select_one("div#result-stats")
    if stats:
        return stats.get_text(strip=True)
    return None


async def _search_via_direct_scrape(
    query: str,
    num: int,
    page: int,
    lang: str,
    country: str | None,
    safe: bool,
    time_range: str | None,
) -> GoogleSearchResponse | None:
    """Fetch Google SERP directly and parse HTML."""
    url = _build_google_url(query, num, page, lang, country, safe, time_range)
    logger.info(f"Direct Google scrape: {url}")

    html = await _fetch_google_html(url)
    if not html:
        return None

    # Check for CAPTCHA/block
    html_lower = html.lower()
    if "captcha" in html_lower or "unusual traffic" in html_lower:
        logger.warning("Google CAPTCHA detected during direct scrape")
        return None

    try:
        result = _parse_google_html(html, query, page, num)
        if result.organic_results:
            return result
        logger.warning(f"Direct scrape parsed 0 results from {len(html)} chars HTML")
    except Exception as e:
        logger.warning(f"Google HTML parsing failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════
# Strategy 3: googlesearch library fallback
# ═══════════════════════════════════════════════════════════════════


async def _search_via_library(
    query: str, num: int, lang: str, country: str | None
) -> GoogleSearchResponse | None:
    """Use googlesearch-python library as basic fallback."""
    try:
        from googlesearch import search as gsearch

        results = []
        kwargs: dict = {
            "num_results": num,
            "lang": lang,
            "advanced": True,
        }
        if country:
            kwargs["region"] = country

        for i, r in enumerate(gsearch(query, **kwargs)):
            results.append(
                GoogleOrganicResult(
                    position=i + 1,
                    title=getattr(r, "title", "") or "",
                    url=getattr(r, "url", "") or "",
                    snippet=getattr(r, "description", "") or "",
                )
            )
            if len(results) >= num:
                break

        if results:
            return GoogleSearchResponse(
                query=query,
                time_taken=0,
                organic_results=results,
            )
    except ImportError:
        logger.debug("googlesearch-python not installed, skipping library fallback")
    except Exception as e:
        logger.warning(f"googlesearch library failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════
# Single-page fetcher (strategy chain for ONE page)
# ═══════════════════════════════════════════════════════════════════

_RESULTS_PER_PAGE = 10  # Google standard page size


async def _fetch_single_page(
    query: str,
    page: int,
    language: str,
    country: str | None,
    safe_search: bool,
    time_range: str | None,
) -> GoogleSearchResponse | None:
    """Fetch one page of results using the strategy chain.

    SearXNG → direct scrape. Returns None if all strategies fail.
    """
    # Strategy 1: SearXNG
    result = await _search_via_searxng(
        query, _RESULTS_PER_PAGE, page, language, time_range
    )
    if result and result.organic_results:
        return result

    # Strategy 2: Direct Google scrape
    result = await _search_via_direct_scrape(
        query, _RESULTS_PER_PAGE, page, language, country, safe_search, time_range
    )
    if result and result.organic_results:
        return result

    return None


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════

_MAX_PAGES = 10  # Safety cap: never fetch more than 10 pages
_PAGE_DELAY = 1.0  # Seconds between page fetches


async def google_search(
    query: str,
    num_results: int = 10,
    page: int = 1,
    language: str = "en",
    country: str | None = None,
    safe_search: bool = False,
    time_range: str | None = None,
) -> GoogleSearchResponse:
    """Search Google and return structured SERP data.

    Fetches multiple pages when num_results > 10 (Google returns ~10 per page).
    Strategy chain per page: SearXNG → direct scrape.
    Final fallback: googlesearch library (handles its own pagination).
    Results are cached in Redis for 5 minutes.
    """
    start = time.time()

    # Check Redis cache
    key = _cache_key(query, num_results, page, language, country, time_range)
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - start, 3)
            logger.info(f"SERP cache hit for '{query}'")
            return GoogleSearchResponse(**data)
    except Exception:
        pass

    # Calculate how many pages we need
    pages_needed = min(
        _MAX_PAGES,
        (num_results + _RESULTS_PER_PAGE - 1) // _RESULTS_PER_PAGE,
    )

    all_organic: list[GoogleOrganicResult] = []
    seen_urls: set[str] = set()  # Deduplicate by URL
    first_page_extras: dict | None = None

    for pg_offset in range(pages_needed):
        current_page = page + pg_offset

        page_result = await _fetch_single_page(
            query, current_page, language, country, safe_search, time_range
        )

        if not page_result or not page_result.organic_results:
            logger.info(
                f"Page {current_page} returned no results, stopping pagination"
            )
            break

        # Collect organic results (deduplicate by URL)
        for r in page_result.organic_results:
            normalized_url = r.url.rstrip("/")
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            r.position = len(all_organic) + 1
            all_organic.append(r)

        logger.info(
            f"Page {current_page}: +{len(page_result.organic_results)} results "
            f"(total: {len(all_organic)})"
        )

        # Save extras from first page only
        if pg_offset == 0:
            first_page_extras = {
                "featured_snippet": page_result.featured_snippet,
                "people_also_ask": page_result.people_also_ask,
                "related_searches": page_result.related_searches,
                "knowledge_panel": page_result.knowledge_panel,
                "total_results": page_result.total_results,
            }

        # Have enough?
        if len(all_organic) >= num_results:
            break

        # Delay between pages to avoid rate-limiting
        if pg_offset < pages_needed - 1:
            await asyncio.sleep(_PAGE_DELAY)

    # If direct methods got nothing, try googlesearch library as final fallback
    if not all_organic:
        logger.info("All page fetches failed, trying googlesearch library fallback")
        lib_result = await _search_via_library(query, num_results, language, country)
        if lib_result and lib_result.organic_results:
            logger.info(
                f"Google SERP via library: {len(lib_result.organic_results)} results"
            )
            all_organic = lib_result.organic_results
            first_page_extras = {
                "featured_snippet": None,
                "people_also_ask": [],
                "related_searches": [],
                "knowledge_panel": None,
                "total_results": None,
            }

    elapsed = round(time.time() - start, 3)

    if not all_organic:
        return GoogleSearchResponse(
            success=False,
            query=query,
            time_taken=elapsed,
        )

    # Trim to requested count
    all_organic = all_organic[:num_results]

    extras = first_page_extras or {}
    result = GoogleSearchResponse(
        query=query,
        total_results=extras.get("total_results"),
        time_taken=elapsed,
        organic_results=all_organic,
        featured_snippet=extras.get("featured_snippet"),
        people_also_ask=extras.get("people_also_ask", []),
        related_searches=extras.get("related_searches", []),
        knowledge_panel=extras.get("knowledge_panel"),
    )

    # Cache the aggregated result
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
