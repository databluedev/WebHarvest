"""Google Images scraper — session-prefixed JSON data parser.

Fetches google.com/search?q=<query>&udm=2 via direct HTTP (no browser needed),
extracts structured image data from session-prefixed JSON blobs embedded in
the HTML response.

Each page returns ~100 unique images. Pagination via `start=N` (step 10)
yields 5-7 pages (~500-600 unique images). When num_results=0, fetches all
pages until exhausted.

Performance: ~100 images in <2s, full exhaust ~10-15s.
Results cached in Redis for 5 minutes.
"""

import hashlib
import json
import logging
import re
import time
from urllib.parse import quote_plus, urlencode

import httpx

from app.config import settings
from app.schemas.data_google import (
    GoogleImageResult,
    GoogleImagesResponse,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_HTTP_TIMEOUT = 30  # seconds
_RESULTS_PER_PAGE = 100  # Google returns ~100 images per page
_PAGE_STEP = 10  # Google Images pagination step (start=0,10,20,...)
_MAX_PAGES = 10  # safety cap: max pages to fetch

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Google's colour filter mapping
_COLOUR_FILTERS = {
    "red": "ic:specific,isc:red",
    "orange": "ic:specific,isc:orange",
    "yellow": "ic:specific,isc:yellow",
    "green": "ic:specific,isc:green",
    "teal": "ic:specific,isc:teal",
    "blue": "ic:specific,isc:blue",
    "purple": "ic:specific,isc:purple",
    "pink": "ic:specific,isc:pink",
    "white": "ic:specific,isc:white",
    "gray": "ic:specific,isc:gray",
    "black": "ic:specific,isc:black",
    "brown": "ic:specific,isc:brown",
}

# Size filter mapping
_SIZE_FILTERS = {
    "large": "isz:l",
    "medium": "isz:m",
    "icon": "isz:i",
}

# Type filter mapping
_TYPE_FILTERS = {
    "photo": "itp:photo",
    "clipart": "itp:clipart",
    "lineart": "itp:lineart",
    "animated": "itp:animated",
}

# Time filter mapping
_TIME_FILTERS = {
    "hour": "qdr:h",
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "year": "qdr:y",
}

# Licence filter mapping
_LICENCE_FILTERS = {
    "creative_commons": "il:cl",
    "commercial": "il:ol",
}

# Aspect ratio filter mapping
_ASPECT_FILTERS = {
    "tall": "iar:t",
    "square": "iar:s",
    "wide": "iar:w",
    "panoramic": "iar:xw",
}


def _cache_key(
    query: str,
    num_results: int,
    language: str,
    country: str | None,
    safe_search: bool,
    colour: str | None,
    size: str | None,
    type_filter: str | None,
    time_range: str | None,
    aspect_ratio: str | None,
    licence: str | None,
) -> str:
    raw = (
        f"gimages:{query}|{num_results}|{language}|{country or ''}|"
        f"{safe_search}|{colour or ''}|{size or ''}|{type_filter or ''}|"
        f"{time_range or ''}|{aspect_ratio or ''}|{licence or ''}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:gimages:{h}"


def _unescape(text: str) -> str:
    """Unescape Google's unicode escapes in inline JS."""
    return (
        text.replace("\\u003d", "=")
        .replace("\\u0026", "&")
        .replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\u0027", "'")
        .replace("\\x3d", "=")
        .replace("\\x26", "&")
        .replace("\\x3c", "<")
        .replace("\\x3e", ">")
        .replace("\\x27", "'")
        .replace("\\/", "/")
    )


# ===================================================================
# URL builder
# ===================================================================


def _build_images_url(
    query: str,
    language: str = "en",
    country: str | None = None,
    safe_search: bool = False,
    colour: str | None = None,
    size: str | None = None,
    type_filter: str | None = None,
    time_range: str | None = None,
    aspect_ratio: str | None = None,
    licence: str | None = None,
) -> str:
    """Build a Google Images search URL with filters."""
    params: list[tuple[str, str]] = [
        ("q", query),
        ("udm", "2"),
        ("hl", language),
    ]

    if country:
        params.append(("gl", country))

    if safe_search:
        params.append(("safe", "active"))

    # Build tbs (tools) parameter for filters
    tbs_parts: list[str] = []

    if colour and colour in _COLOUR_FILTERS:
        tbs_parts.append(_COLOUR_FILTERS[colour])

    if size and size in _SIZE_FILTERS:
        tbs_parts.append(_SIZE_FILTERS[size])

    if type_filter and type_filter in _TYPE_FILTERS:
        tbs_parts.append(_TYPE_FILTERS[type_filter])

    if time_range and time_range in _TIME_FILTERS:
        tbs_parts.append(_TIME_FILTERS[time_range])

    if aspect_ratio and aspect_ratio in _ASPECT_FILTERS:
        tbs_parts.append(_ASPECT_FILTERS[aspect_ratio])

    if licence and licence in _LICENCE_FILTERS:
        tbs_parts.append(_LICENCE_FILTERS[licence])

    if tbs_parts:
        params.append(("tbs", ",".join(tbs_parts)))

    qs = urlencode(params, quote_via=quote_plus)
    return f"https://www.google.com/search?{qs}"


# ===================================================================
# Parser — session-prefixed JSON extractor
# ===================================================================


def _parse_images_from_response(html: str) -> list[GoogleImageResult]:
    """Extract structured image data from Google Images HTML response.

    Google Images embeds image data in script blocks as session-prefixed JSON
    keys. There are two entry types:
      - Type 1 (loaded): entry[1][1]=doc_id, entry[1][2]=thumb, entry[1][3]=full
      - Type 0 (lazy):   entry[1]=doc_id, entry[2]=thumb, entry[3]=full

    Both contain the same 100 images. We parse using regex to extract the
    structured data without needing a full JS parser.
    """
    text = _unescape(html)

    # Find the session prefix — pattern: "PREFIX_N":[0, or "PREFIX_N":[1,
    prefix_match = re.search(r'"([a-zA-Z0-9_-]{20,}?)(\d+)":\s*\[', text)
    if not prefix_match:
        logger.warning("Google Images: no session prefix found in response")
        return []

    prefix = prefix_match.group(1)
    logger.debug("Google Images: session prefix = %s", prefix)

    # Extract image entries using regex
    # Matches both type 0 and type 1 entries
    pattern = re.compile(
        rf'"{re.escape(prefix)}\d+":\s*\[\s*(?:1,\s*\[)?\s*(\d+)\s*,\s*"([a-zA-Z0-9_-]+)"\s*,'
        rf'\s*\["(https://encrypted-tbn0\.gstatic\.com/images\?[^"]+)",\s*(\d+),\s*(\d+)\]\s*,'
        rf'\s*\["([^"]+)",\s*(\d+),\s*(\d+)\]'
        rf'(?:\s*,\s*null\s*,\s*\d+\s*,\s*"(rgb\([^"]*\))")?'
    )

    seen_doc_ids: set[str] = set()
    results: list[GoogleImageResult] = []
    position = 0

    for m in pattern.finditer(text):
        doc_id = m.group(2)
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        position += 1

        # Core image data
        thumbnail_url = m.group(3)
        thumbnail_width = int(m.group(4))
        thumbnail_height = int(m.group(5))
        full_url = m.group(6)
        full_width = int(m.group(7))
        full_height = int(m.group(8))
        dominant_color = m.group(9) if m.group(9) else None

        # Extract metadata from the block following the image data
        pos = m.end()
        chunk = text[pos: pos + 2000]

        # "2000": [null, "domain.com", "filesize"]
        domain = None
        file_size = None
        meta_2000 = re.search(r'"2000":\s*\[null\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\]', chunk)
        if meta_2000:
            domain = meta_2000.group(1)
            file_size = meta_2000.group(2)

        # "2003": [null, "ref_docid", "source_url", "title", ...]
        source_url = None
        title = None
        site_name = None
        meta_2003 = re.search(
            r'"2003":\s*\[null\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"',
            chunk,
        )
        if meta_2003:
            source_url = meta_2003.group(2)
            title = meta_2003.group(3)

        # Site name at index 12 in the 2003 array
        site_match = re.search(r'"2003":\[(?:[^]]*?,){12}"([^"]+)"', chunk)
        if site_match:
            site_name = site_match.group(1)

        # "2008": [null, "short_title"]
        short_title = None
        meta_2008 = re.search(r'"2008":\s*\[null\s*,\s*"([^"]+)"\]', chunk)
        if meta_2008:
            short_title = meta_2008.group(1)

        # "2006": licence info [...[11][0]=licence_page, [11][1]=licence_url, [11][3]=licensor]
        licence_page = None
        licence_url = None
        licensor = None
        meta_2006 = re.search(
            r'"2006":\[(?:[^]]*?\[){1,12}"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*\d+\s*,\s*"([^"]+)"',
            chunk,
        )
        if meta_2006:
            licence_page = meta_2006.group(1)
            licence_url = meta_2006.group(2)
            licensor = meta_2006.group(3)

        # Use short_title as fallback for title
        display_title = title or short_title

        results.append(
            GoogleImageResult(
                position=position,
                title=display_title or "Untitled",
                url=source_url or full_url,
                image_url=full_url,
                image_width=full_width,
                image_height=full_height,
                thumbnail_url=thumbnail_url,
                thumbnail_width=thumbnail_width,
                thumbnail_height=thumbnail_height,
                domain=domain,
                file_size=file_size,
                site_name=site_name,
                dominant_color=dominant_color,
                doc_id=doc_id,
                licence_page=licence_page,
                licence_url=licence_url,
                licensor=licensor,
            )
        )

    logger.info("Google Images: parsed %d unique images", len(results))
    return results


# ===================================================================
# HTTP fetch
# ===================================================================


async def _fetch_images_html(url: str, client: httpx.AsyncClient) -> str | None:
    """Fetch Google Images search page via HTTP GET."""
    try:
        resp = await client.get(url, headers=_REQUEST_HEADERS)
        if resp.status_code == 200:
            return resp.text
        logger.warning("Google Images HTTP %d for %s", resp.status_code, url[:120])
        return None
    except Exception as e:
        logger.warning("Google Images HTTP error: %s", e)
        return None


def _is_blocked(html: str) -> bool:
    low = html.lower()
    return "unusual traffic" in low or "captcha" in low


# ===================================================================
# Main entry point
# ===================================================================


async def google_images(
    query: str,
    num_results: int = 0,
    language: str = "en",
    country: str | None = None,
    safe_search: bool = False,
    colour: str | None = None,
    size: str | None = None,
    type_filter: str | None = None,
    time_range: str | None = None,
    aspect_ratio: str | None = None,
    licence: str | None = None,
) -> GoogleImagesResponse:
    """Fetch Google Images results with structured data.

    Uses direct HTTP GET (no browser). Each page returns ~100 images.
    Pagination via `start=N` (step 10) fetches subsequent pages.

    num_results=0 means fetch ALL pages until exhausted.
    Results cached in Redis for 5 minutes.
    """
    t0 = time.time()
    unlimited = num_results == 0

    # Check Redis cache
    key = _cache_key(
        query, num_results, language, country, safe_search,
        colour, size, type_filter, time_range, aspect_ratio, licence,
    )
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - t0, 3)
            logger.info("Images cache hit for '%s'", query)
            return GoogleImagesResponse(**data)
    except Exception:
        pass

    # Build base URL (no start param yet)
    base_url = _build_images_url(
        query, language, country, safe_search,
        colour, size, type_filter, time_range, aspect_ratio, licence,
    )

    all_images: list[GoogleImageResult] = []
    seen_doc_ids: set[str] = set()
    pages_fetched = 0

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_HTTP_TIMEOUT,
    ) as client:
        for page_idx in range(_MAX_PAGES):
            # Build paginated URL
            url = base_url if page_idx == 0 else f"{base_url}&start={page_idx * _PAGE_STEP}"

            html = await _fetch_images_html(url, client)
            if not html:
                break

            if _is_blocked(html):
                logger.warning("Google Images: CAPTCHA/block on page %d for '%s'", page_idx + 1, query)
                break

            page_images = _parse_images_from_response(html)
            pages_fetched += 1

            # Deduplicate across pages
            new_count = 0
            for img in page_images:
                if img.doc_id not in seen_doc_ids:
                    seen_doc_ids.add(img.doc_id)
                    all_images.append(img)
                    new_count += 1

            logger.info(
                "Google Images page %d: %d parsed, %d new (total %d)",
                page_idx + 1, len(page_images), new_count, len(all_images),
            )

            # Stop conditions
            if not page_images:
                break  # exhausted
            if not unlimited and len(all_images) >= num_results:
                break  # got enough

    elapsed = round(time.time() - t0, 3)

    if not all_images:
        return GoogleImagesResponse(
            success=False, query=query, time_taken=elapsed,
        )

    # Trim to requested count (if not unlimited)
    if not unlimited:
        all_images = all_images[:num_results]

    # Number positions sequentially
    for i, img in enumerate(all_images):
        img.position = i + 1

    logger.info(
        "Google Images: %d images for '%s' in %.1fs (%d pages)",
        len(all_images), query, elapsed, pages_fetched,
    )

    result = GoogleImagesResponse(
        query=query,
        total_results=len(all_images),
        time_taken=elapsed,
        images=all_images,
    )

    # Cache in Redis
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
