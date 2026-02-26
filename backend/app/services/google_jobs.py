"""Google Jobs (Careers) scraper — reverse-engineered AF_initDataCallback parser.

Fetches google.com/about/careers/applications/jobs/results via direct HTTP
(no browser needed), extracts the AF_initDataCallback ds:1 blob which
contains structured job data.

The server returns page-specific data for each ?page=N parameter — the
AF_initDataCallback contains different job entries per page (20 per page).
This allows fully parallel pagination via httpx without any browser.

Performance: ~200 jobs in 2.5s, ~2000 jobs in ~25s (parallel HTTP GET).
Results cached in Redis for 5 minutes.
"""

import asyncio
import datetime
import hashlib
import json
import logging
import re
import time
from math import ceil
from urllib.parse import quote_plus, urlencode

import httpx

from app.config import settings
from app.schemas.data_google import (
    GoogleJobListing,
    GoogleJobLocation,
    GoogleJobsResponse,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_PAGE_SIZE = 20  # Google Careers returns 20 per page
_MAX_CONSECUTIVE_EMPTY = 3  # Stop after N batches with 0 new jobs
_PARALLEL_PAGES = 10  # Pages fetched concurrently per batch
_HTTP_TIMEOUT = 30  # seconds per request

# Experience level mapping: internal int → display string
_EXPERIENCE_LEVELS = {
    1: "Entry",
    2: "Mid",
    3: "Advanced",
    4: "Director",
}

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _cache_key(
    query: str,
    num_results: int,
    has_remote: bool | None,
    target_level: list[str] | None,
    employment_type: list[str] | None,
    company: list[str] | None,
    sort_by: str,
) -> str:
    raw = (
        f"jobs:{query}|{num_results}|{has_remote}|"
        f"{','.join(sorted(target_level or []))}|"
        f"{','.join(sorted(employment_type or []))}|"
        f"{','.join(sorted(company or []))}|{sort_by}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:gjobs:{h}"


def _safe_get(data: list | None, *indices, default=None):
    """Safely traverse nested lists by index chain."""
    current = data
    for idx in indices:
        if not isinstance(current, list) or idx >= len(current):
            return default
        current = current[idx]
    return current if current is not None else default


# ===================================================================
# URL builder
# ===================================================================


def _build_jobs_url(
    query: str,
    page: int = 1,
    has_remote: bool | None = None,
    target_level: list[str] | None = None,
    employment_type: list[str] | None = None,
    company: list[str] | None = None,
    location: list[str] | None = None,
    degree: str | None = None,
    skills: str | None = None,
    sort_by: str = "relevance",
) -> str:
    """Build a Google Careers search URL with filters."""
    params: list[tuple[str, str]] = [
        ("q", query),
        ("sort_by", sort_by),
    ]

    if page > 1:
        params.append(("page", str(page)))

    if has_remote:
        params.append(("has_remote", "true"))

    if target_level:
        for level in target_level:
            params.append(("target_level", level))

    if employment_type:
        for emp in employment_type:
            params.append(("employment_type", emp))

    if company:
        for comp in company:
            params.append(("company", comp))

    if location:
        for loc in location:
            params.append(("location", loc))

    if degree:
        params.append(("degree", degree))

    if skills:
        params.append(("skills", skills))

    qs = urlencode(params, quote_via=quote_plus)
    return f"https://www.google.com/about/careers/applications/jobs/results?{qs}"


# ===================================================================
# AF_initDataCallback extractor + parser
# ===================================================================

# Field index mapping (reverse-engineered from AF_initDataCallback ds:1):
#   ds1[0]  = list of job entries (page of results)
#   ds1[2]  = total result count across ALL pages
#   ds1[3]  = page size (20)
#
# Per job entry (21 fields):
#   [0]  = job_id (str, numeric)
#   [1]  = title
#   [2]  = apply_url (sign-in URL with jobId param)
#   [3]  = [None, responsibilities_html]
#   [4]  = [None, combined_qualifications_html]
#   [5]  = company_id (Cloud Talent resource path)
#   [7]  = company_name ("Google", "DeepMind", etc.)
#   [8]  = language_code ("en-US")
#   [9]  = locations list (see below)
#   [10] = [None, description_html]
#   [11] = category_ids (list of ints)
#   [12] = [epoch_seconds, nanoseconds] — created_at
#   [13] = [epoch_seconds, nanoseconds] — updated_at
#   [14] = [epoch_seconds, nanoseconds] — published_at
#   [15] = [None, benefits_html] or ""
#   [18] = [None, additional_info_html] or ""
#   [19] = [None, min_qualifications_only_html]
#   [20] = experience_level (1=Entry, 2=Mid, 3=Advanced, 4=Director)
#
# Location sub-structure [9][j]:
#   [0] = display_name ("Kirkland, WA, USA")
#   [2] = city
#   [3] = postal_code
#   [4] = state/region
#   [5] = country_code


def _extract_af_init_data(html: str) -> list[dict] | None:
    """Extract AF_initDataCallback blobs from Google Careers HTML."""
    header_pattern = re.compile(
        r"AF_initDataCallback\(\{key:\s*'([^']+)',\s*hash:\s*'[^']*',\s*data:",
    )

    results = []
    for match in header_pattern.finditer(html):
        key = match.group(1)
        data_start = match.end()

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


def _parse_timestamp(ts_field) -> str | None:
    """Convert protobuf timestamp [epoch_seconds, nanoseconds] to ISO string."""
    if not ts_field or not isinstance(ts_field, list) or not ts_field[0]:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(ts_field[0], tz=datetime.timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError, TypeError):
        return None


def _parse_html_field(field) -> str | None:
    """Extract HTML string from [None, html_string] or bare string."""
    if not field:
        return None
    if isinstance(field, list) and len(field) > 1 and isinstance(field[1], str):
        return field[1] if field[1] else None
    if isinstance(field, str) and field:
        return field
    return None


def _slugify(text: str) -> str:
    """Convert title to URL slug for detail URL."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug


def _parse_job_entry(entry: list, position: int) -> GoogleJobListing | None:
    """Parse a single job entry from ds:1 into GoogleJobListing."""
    try:
        job_id = entry[0] if len(entry) > 0 else None
        if not job_id or not isinstance(job_id, str):
            return None

        title = entry[1] if len(entry) > 1 else None
        if not title or not isinstance(title, str):
            return None

        company = entry[7] if len(entry) > 7 and isinstance(entry[7], str) else "Google"

        # Apply URL
        apply_url = entry[2] if len(entry) > 2 and isinstance(entry[2], str) else None

        # Detail URL
        detail_url = (
            f"https://www.google.com/about/careers/applications/jobs/results/"
            f"{job_id}-{_slugify(title)}"
        )

        # Locations
        locations: list[GoogleJobLocation] = []
        raw_locations = entry[9] if len(entry) > 9 and isinstance(entry[9], list) else []
        for loc in raw_locations:
            if isinstance(loc, list) and loc:
                locations.append(
                    GoogleJobLocation(
                        display_name=loc[0] if loc[0] else "Unknown",
                        city=loc[2] if len(loc) > 2 else None,
                        state=loc[4] if len(loc) > 4 else None,
                        country=loc[5] if len(loc) > 5 else None,
                        postal_code=loc[3] if len(loc) > 3 else None,
                    )
                )

        # HTML fields
        description_html = _parse_html_field(entry[10] if len(entry) > 10 else None)
        responsibilities_html = _parse_html_field(entry[3] if len(entry) > 3 else None)
        qualifications_html = _parse_html_field(entry[4] if len(entry) > 4 else None)
        min_qualifications_html = _parse_html_field(entry[19] if len(entry) > 19 else None)
        benefits_html = _parse_html_field(entry[15] if len(entry) > 15 else None)

        # Category IDs
        category_ids = entry[11] if len(entry) > 11 and isinstance(entry[11], list) else None

        # Timestamps
        created_at = _parse_timestamp(entry[12] if len(entry) > 12 else None)
        updated_at = _parse_timestamp(entry[13] if len(entry) > 13 else None)

        # Experience level
        exp_raw = entry[20] if len(entry) > 20 else None
        experience_level = _EXPERIENCE_LEVELS.get(exp_raw) if isinstance(exp_raw, int) else None

        return GoogleJobListing(
            position=position,
            job_id=job_id,
            title=title,
            company=company,
            locations=locations,
            apply_url=apply_url,
            detail_url=detail_url,
            description_html=description_html,
            responsibilities_html=responsibilities_html,
            qualifications_html=qualifications_html,
            min_qualifications_html=min_qualifications_html,
            benefits_html=benefits_html,
            experience_level=experience_level,
            category_ids=category_ids,
            created_at=created_at,
            updated_at=updated_at,
        )

    except Exception as e:
        logger.debug("Failed to parse job entry at position %d: %s", position, e)
        return None


def _parse_jobs_blob(af_blobs: list[dict]) -> tuple[list[GoogleJobListing], int | None, list[str]]:
    """Extract jobs from AF_initDataCallback ds:1 blob.

    Returns: (jobs, total_count, companies)
    """
    # Extract company list from ds:0 — structure: ds0[0] = [[resource_id, name, ...], ...]
    companies: list[str] = []
    for blob in af_blobs:
        if blob["key"] == "ds:0":
            data = blob["data"]
            entries = _safe_get(data, 0)
            if entries and isinstance(entries, list):
                for entry in entries:
                    name = _safe_get(entry, 1)
                    if name and isinstance(name, str):
                        companies.append(name)
            break

    # Find ds:1 (job data)
    ds1 = None
    for blob in af_blobs:
        if blob["key"] == "ds:1":
            ds1 = blob["data"]
            break

    if ds1 is None:
        logger.warning("No ds:1 blob found in AF_initDataCallback")
        return [], None, companies

    # ds1[0] = job entries, ds1[2] = total count, ds1[3] = page size
    entries = ds1[0] if isinstance(ds1, list) and ds1 else []
    total_count = ds1[2] if isinstance(ds1, list) and len(ds1) > 2 else None

    if not entries or not isinstance(entries, list):
        logger.warning("ds:1[0] is empty or not a list")
        return [], total_count, companies

    jobs: list[GoogleJobListing] = []
    for i, entry in enumerate(entries):
        if isinstance(entry, list):
            job = _parse_job_entry(entry, position=i + 1)
            if job:
                jobs.append(job)

    return jobs, total_count, companies


# ===================================================================
# HTTP fetch + parallel pagination
# ===================================================================


async def _fetch_page_html(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    """Fetch a single page via HTTP GET and return HTML."""
    try:
        resp = await client.get(url, headers=_REQUEST_HEADERS)
        if resp.status_code == 200:
            return resp.text
        logger.warning("Google Jobs HTTP %d for %s", resp.status_code, url[:100])
        return None
    except Exception as e:
        logger.warning("Google Jobs HTTP error: %s", e)
        return None


async def _fetch_and_parse(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[list[GoogleJobListing], int | None, list[str]]:
    """Fetch a page and parse AF_initDataCallback."""
    html = await _fetch_page_html(client, url)
    if not html:
        return [], None, []

    af_blobs = _extract_af_init_data(html)
    if not af_blobs:
        return [], None, []

    return _parse_jobs_blob(af_blobs)


async def _fetch_all_pages(
    query: str,
    num_results: int,
    has_remote: bool | None,
    target_level: list[str] | None,
    employment_type: list[str] | None,
    company: list[str] | None,
    location: list[str] | None,
    degree: str | None,
    skills: str | None,
    sort_by: str,
) -> tuple[list[GoogleJobListing], int | None, list[str]]:
    """Fetch job pages via parallel HTTP GET.

    1. Fetch page 1 to get initial jobs + total count + companies
    2. Calculate pages needed
    3. Fetch remaining pages in parallel batches of _PARALLEL_PAGES
    4. Dedup by job_id, stop on consecutive empty batches
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_HTTP_TIMEOUT,
    ) as client:
        # ── Page 1 ──
        url1 = _build_jobs_url(
            query, 1, has_remote, target_level, employment_type,
            company, location, degree, skills, sort_by,
        )
        logger.info("Google Jobs page 1: %s", url1)

        jobs_p1, total_count, companies = await _fetch_and_parse(client, url1)
        if not jobs_p1:
            return [], total_count, companies

        all_jobs: list[GoogleJobListing] = list(jobs_p1)
        seen_ids: set[str] = {j.job_id for j in all_jobs}

        logger.info(
            "Google Jobs page 1: %d jobs (total available: %s)",
            len(all_jobs), total_count,
        )

        if not total_count or len(all_jobs) >= num_results:
            return all_jobs, total_count, companies

        # ── Calculate remaining pages ──
        target = min(num_results, total_count)
        pages_needed = ceil(target / _PAGE_SIZE)
        remaining_pages = list(range(2, pages_needed + 1))

        consecutive_empty_batches = 0

        # ── Fetch in parallel batches ──
        for batch_start in range(0, len(remaining_pages), _PARALLEL_PAGES):
            if len(all_jobs) >= num_results:
                break
            if consecutive_empty_batches >= _MAX_CONSECUTIVE_EMPTY:
                logger.info("Google Jobs: %d consecutive empty batches, stopping", consecutive_empty_batches)
                break

            batch = remaining_pages[batch_start : batch_start + _PARALLEL_PAGES]

            urls = [
                _build_jobs_url(
                    query, pg, has_remote, target_level, employment_type,
                    company, location, degree, skills, sort_by,
                )
                for pg in batch
            ]

            tasks = [_fetch_and_parse(client, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            new_in_batch = 0
            for page_result in results:
                if isinstance(page_result, Exception):
                    logger.warning("Google Jobs page fetch error: %s", page_result)
                    continue

                page_jobs, _, _ = page_result
                for job in page_jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                        new_in_batch += 1

            logger.info(
                "Google Jobs pages %d-%d: +%d new (total: %d)",
                batch[0], batch[-1], new_in_batch, len(all_jobs),
            )

            if new_in_batch == 0:
                consecutive_empty_batches += 1
            else:
                consecutive_empty_batches = 0

        return all_jobs, total_count, companies


# ===================================================================
# Main entry point
# ===================================================================


async def google_jobs(
    query: str,
    num_results: int = 100,
    has_remote: bool | None = None,
    target_level: list[str] | None = None,
    employment_type: list[str] | None = None,
    company: list[str] | None = None,
    location: list[str] | None = None,
    degree: str | None = None,
    skills: str | None = None,
    sort_by: str = "relevance",
) -> GoogleJobsResponse:
    """Fetch Google Careers job listings with parallel HTTP pagination.

    Uses direct HTTP GET requests (no browser) to fetch all pages in parallel.
    The server embeds page-specific AF_initDataCallback data for each ?page=N.

    Performance: ~200 jobs in ~3s, ~2000 jobs in ~25s.
    Results cached in Redis for 5 minutes.
    """
    start = time.time()

    # Check Redis cache
    key = _cache_key(query, num_results, has_remote, target_level, employment_type, company, sort_by)
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            data = json.loads(cached)
            data["time_taken"] = round(time.time() - start, 3)
            logger.info("Jobs cache hit for '%s'", query)
            return GoogleJobsResponse(**data)
    except Exception:
        pass

    # Fetch all pages via parallel HTTP
    all_jobs, total_count, companies = await _fetch_all_pages(
        query, num_results, has_remote, target_level, employment_type,
        company, location, degree, skills, sort_by,
    )

    elapsed = round(time.time() - start, 3)

    if not all_jobs:
        logger.warning("Google Jobs: 0 jobs for '%s'", query)
        return GoogleJobsResponse(
            success=False, query=query, time_taken=elapsed,
            total_results=total_count, companies=companies or None,
        )

    # Trim and re-number
    all_jobs = all_jobs[:num_results]
    for i, job in enumerate(all_jobs):
        job.position = i + 1

    logger.info(
        "Google Jobs: %d jobs fetched (total %s) for '%s' in %.1fs",
        len(all_jobs), total_count, query, elapsed,
    )

    result = GoogleJobsResponse(
        query=query,
        total_results=total_count,
        time_taken=elapsed,
        jobs=all_jobs,
        companies=companies or None,
    )

    # Cache in Redis
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
