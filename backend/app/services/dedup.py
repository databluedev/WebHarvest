"""URL deduplication and normalization service."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


# Exact-match tracking parameters to strip
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "twclid",
    "li_fat_id",
    "mc_cid",
    "mc_eid",
    "ref",
    "_ref",
    "ref_src",
    "ref_url",
    "si",
    "s",
    "share",
    "igshid",
    "oly_enc_id",
    "oly_anon_id",
    "vero_id",
    "wickedid",
    "__hstc",
    "__hssc",
    "__hsfp",
    "hsCtaTracking",
    "_ga",
    "_gl",
    "_hsenc",
    "_openstat",
    "nb_klid",
    "plan",
    "guccounter",
}

# Generic pattern-based param stripping — catches session/personalization
# params across any site without hardcoding site-specific names.
#
# Matches params whose values look like:
#   - UUID anywhere in value   (exact or embedded like amzn1.sym.<uuid>)
#   - Hex session IDs          (≥16 hex chars)
#   - Base64-ish blobs         (≥20 chars of alphanumeric + /+=_-)
#
# These are almost always session tokens, request IDs, or personalization
# context that don't affect page content — safe to strip for dedup.
_SESSION_VALUE_RE = re.compile(
    r"^[0-9a-f]{16,}$"                                                    # hex ID (exact)
    r"|^[A-Za-z0-9+/=_-]{20,}$"                                           # base64 blob (exact)
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",   # UUID (anywhere)
    re.IGNORECASE,
)


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication (Firecrawl-style permutation dedup).

    - Lowercase scheme and host
    - Strip www. prefix (www.example.com == example.com)
    - Remove trailing slash (unless path is just /)
    - Strip index.html / index.htm (same page as directory)
    - Sort query params
    - Strip tracking params (utm_*, fbclid, gclid, etc.)
    - Remove fragments
    - Collapse // in path
    - Remove default ports (80 for http, 443 for https)
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url.strip()

    # Lowercase scheme and host
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port

    # Remove default ports
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    # Strip www. prefix for dedup (www.example.com == example.com)
    if host.startswith("www."):
        host = host[4:]

    netloc = host
    if port:
        netloc = f"{host}:{port}"
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        netloc = f"{userinfo}@{netloc}"

    # Normalize path
    path = parsed.path or "/"
    # Collapse double slashes
    path = re.sub(r"/{2,}", "/", path)
    # Remove trailing slash (but keep root /)
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # Strip index.html / index.htm (same page as directory)
    path = re.sub(r"/index\.html?$", "", path) or "/"

    # Param names that commonly hold content IDs (not session tokens) — never strip
    _CONTENT_ID_PARAMS = {
        "id", "product_id", "productid", "item_id", "itemid", "sku",
        "asin", "isbn", "upc", "ean", "article_id", "articleid",
        "post_id", "postid", "doc_id", "docid", "ref", "variant",
        "variant_id", "variantid", "catalog_id", "catalogid",
    }

    # Sort and filter query params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {}
    for k, v in sorted(query_params.items()):
        if k.lower() in _TRACKING_PARAMS:
            continue
        # Strip params whose values look like session IDs / UUIDs / base64 blobs,
        # but preserve params whose names indicate content identifiers
        if k.lower() not in _CONTENT_ID_PARAMS and v and _SESSION_VALUE_RE.search(v[0]):
            continue
        filtered_params[k] = v
    query = urlencode(filtered_params, doseq=True) if filtered_params else ""

    # Remove fragment
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Normalize and deduplicate a list of URLs, preserving order.

    Returns the first occurrence of each normalized URL.
    """
    seen: dict[str, str] = {}  # normalized -> original
    for url in urls:
        url = url.strip()
        if not url:
            continue
        norm = normalize_url(url)
        if norm not in seen:
            seen[norm] = url
    return list(seen.values())


# Navigation/pagination params that don't change page content — safe to strip
# for crawl dedup.  Content-bearing params (color, size, brand, category,
# price, rating, filter, facet, min_price, max_price, price_range) are
# intentionally NOT included — they produce different product variants on
# e-commerce sites and must be preserved.
_NAVIGATION_PARAMS = {
    "page", "p", "pg", "offset", "start", "limit", "per_page",
    "sort", "order", "orderby", "sortby", "dir", "direction",
    "view", "display", "layout", "tab", "section",
    "lang", "language", "locale", "hl",
}


def normalize_url_for_crawl(url: str) -> str:
    """Normalize URL for crawl dedup — strips navigation/faceted params.

    More aggressive than normalize_url() because crawl dedup cares about
    content uniqueness, not URL identity.
    """
    base = normalize_url(url)
    try:
        parsed = urlparse(base)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {
            k: v for k, v in query_params.items()
            if k.lower() not in _NAVIGATION_PARAMS
        }
        query = urlencode(filtered, doseq=True) if filtered else ""
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            "", query, ""
        ))
    except Exception:
        return base


def _is_faceted_variation(url: str, base_url: str) -> bool:
    """Check if url is a faceted/filtered variation of base_url.

    Returns True if the only difference is faceted query params.
    """
    norm1 = normalize_url_for_crawl(url)
    norm2 = normalize_url_for_crawl(base_url)
    return norm1 == norm2


def filter_faceted_urls(urls: list[str]) -> list[str]:
    """Deduplicate URLs that differ only by faceted/navigation params.

    Returns one URL per unique crawl-normalized form (first occurrence).
    """
    seen: dict[str, str] = {}
    for url in urls:
        key = normalize_url_for_crawl(url)
        if key not in seen:
            seen[key] = url
    return list(seen.values())


async def check_redis_seen(redis, job_id: str, url: str) -> bool:
    """Check if a URL has been seen for a given job using Redis SET.

    Returns True if the URL was already seen (already in the set).
    Returns False if it's new (just added).
    """
    normalized = normalize_url(url)
    # SADD returns 0 if already exists, 1 if newly added
    added = await redis.sadd(f"job:{job_id}:seen", normalized)
    return added == 0  # True means already seen
