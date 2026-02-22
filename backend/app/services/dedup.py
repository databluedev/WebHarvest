"""URL deduplication and normalization service."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


# Tracking parameters to strip
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

    # Sort and filter query params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {
        k: v
        for k, v in sorted(query_params.items())
        if k.lower() not in _TRACKING_PARAMS
    }
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


async def check_redis_seen(redis, job_id: str, url: str) -> bool:
    """Check if a URL has been seen for a given job using Redis SET.

    Returns True if the URL was already seen (already in the set).
    Returns False if it's new (just added).
    """
    normalized = normalize_url(url)
    # SADD returns 0 if already exists, 1 if newly added
    added = await redis.sadd(f"job:{job_id}:seen", normalized)
    return added == 0  # True means already seen
