#!/usr/bin/env python3
"""Reverse-engineer Google Careers AF_initDataCallback ds:1 blob for job listings.

Parses jobs_page.html to extract the full AF_initDataCallback data, maps every
field index, and prints a comprehensive analysis with stats.

=============================================================================
AF_initDataCallback FIELD INDEX MAPPING — Google Careers (ds:1)
=============================================================================

ds:1 TOP-LEVEL STRUCTURE:
    ds1[0]  : list[N]  — Array of job entries (N = page size, typically 20)
    ds1[1]  : None     — Reserved / unused
    ds1[2]  : int      — Total result count across ALL pages (e.g. 1963)
    ds1[3]  : int      — Page size (e.g. 20)

EACH JOB ENTRY (ds1[0][i]) is a list of 21 elements:

    Index  | Type              | Field Name               | Description
    -------|-------------------|--------------------------|--------------------------------------------
    [0]    | str               | job_id                   | Numeric job ID (e.g. "85809587231302342")
    [1]    | str               | title                    | Full job title
    [2]    | str               | apply_url                | Direct sign-in/apply URL with encoded jobId param
    [3]    | [None, str]       | responsibilities_html    | Job responsibilities as HTML <ul>/<li>
    [4]    | [None, str]       | qualifications_html      | Combined min + preferred qualifications HTML
           |                   |                          | Contains <h3>Minimum qualifications:</h3> and
           |                   |                          | <h3>Preferred qualifications:</h3> sections
    [5]    | str               | company_id               | Cloud Talent Solution company resource path
           |                   |                          | e.g. "projects/gweb-careers-proto/tenants/.../companies/..."
    [6]    | None              | (reserved)               | Always None in observed data
    [7]    | str               | company_name             | Display name (e.g. "Google", "DeepMind")
    [8]    | str               | language_code            | Locale (e.g. "en-US")
    [9]    | list[list]        | locations                | Array of location entries, each:
           |                   |                          |   [0] display_name  (e.g. "Kirkland, WA, USA")
           |                   |                          |   [1] addresses     (list of full street addresses)
           |                   |                          |   [2] city          (e.g. "Kirkland")
           |                   |                          |   [3] postal_code   (e.g. "98033" or None)
           |                   |                          |   [4] state_region  (e.g. "WA", "Masovian Voivodeship")
           |                   |                          |   [5] country_code  (e.g. "US", "PL", "SG")
    [10]   | [None, str]       | description_html         | Full job description/overview as HTML
    [11]   | list[int]         | category_ids             | Job category/skill codes (observed: 2, 3, 4)
           |                   |                          | Likely maps to Google's internal taxonomy:
           |                   |                          |   2 = Software Engineering
           |                   |                          |   3 = Technical Infrastructure
           |                   |                          |   4 = Data Science & Analytics (or similar)
           |                   |                          | Multiple values = cross-functional role
    [12]   | [int, int]        | created_at               | Protobuf Timestamp [seconds, nanos] — original post date
    [13]   | [int, int]        | updated_at               | Protobuf Timestamp [seconds, nanos] — last modified/refreshed
    [14]   | [int, int]        | published_at             | Protobuf Timestamp [seconds, nanos] — publish time
           |                   |                          | (typically within 0-1s of updated_at)
    [15]   | [None, str]       | benefits_html            | Benefits/compensation info as HTML (US roles) or ""
    [16]   | None              | (reserved)               | Always None in observed data
    [17]   | None              | (reserved)               | Always None in observed data
    [18]   | [None, str]       | additional_info_html     | Location preference note or "" — e.g.
           |                   |                          | "Note: By applying to this position you will have
           |                   |                          |  an opportunity to share your preferred working
           |                   |                          |  location from the following: <b>City, State</b>."
    [19]   | [None, str]       | min_qualifications_html  | ONLY minimum qualifications as HTML <ul>/<li>
           |                   |                          | (without headers — subset of field [4])
    [20]   | int               | experience_level         | Experience level enum:
           |                   |                          |   1 = Entry
           |                   |                          |   2 = Mid
           |                   |                          |   3 = Advanced
           |                   |                          |   4 = Director (inferred from Google Careers UI)

LOCATION SUB-STRUCTURE (field [9][j]):
    [0] display_name  : str       — "Kirkland, WA, USA"
    [1] addresses     : list[str] — ["451 7th Ave S, Kirkland, WA 98033, USA"]
    [2] city          : str       — "Kirkland"
    [3] postal_code   : str|None  — "98033" (None for non-US)
    [4] state_region  : str       — "WA" or "Masovian Voivodeship"
    [5] country_code  : str       — "US", "PL", "SG", "IN", "MX"

TIMESTAMP FORMAT:
    Protobuf google.protobuf.Timestamp = [seconds_since_epoch, nanoseconds]
    Convert: datetime.fromtimestamp(field[0])

ds:0 STRUCTURE (Company/Organization List):
    ds0[0] is a list of company entries, each:
        [0] company_resource_id  — "projects/gweb-careers-proto/tenants/.../companies/UUID"
        [1] display_name         — "Google", "DeepMind", "YouTube", etc.
        [2] slug                 — "google", "deepmind", "youtube"
        [3] website_url          — (optional) company website
        [4] careers_url          — (optional) company careers page
        [5] logo_url             — (optional) company logo image URL

JOB DETAIL PAGE URL CONSTRUCTION:
    Base: https://www.google.com/about/careers/applications/jobs/results/
    Pattern: {base}/{job_id}-{slugified_title}
    Example: .../jobs/results/85809587231302342-software-engineer-bigquery-ai-developer-experience

EXTRACTING PREFERRED QUALIFICATIONS from field [4]:
    Split on "<h3>Preferred qualifications:</h3>" — everything after is preferred.
    Field [19] contains ONLY the minimum qualifications (without headers).
    To get preferred only: parse [4], extract text after "Preferred qualifications:" header.

=============================================================================
"""

import json
import re
import sys
import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPERIENCE_LEVEL_MAP = {
    1: "Entry",
    2: "Mid",
    3: "Advanced",
    4: "Director",
}

CATEGORY_MAP = {
    2: "Software Engineering",
    3: "Technical Infrastructure",
    4: "Data Science & Analytics",
}

BASE_DETAIL_URL = "https://www.google.com/about/careers/applications/jobs/results"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_af_init_data(html: str) -> list[dict]:
    """Extract all AF_initDataCallback blobs from HTML."""
    pattern = r'AF_initDataCallback\s*\(\s*\{(.*?)\}\s*\)\s*;'
    blobs = []
    for m in re.finditer(pattern, html, re.DOTALL):
        content = m.group(1)
        key_match = re.search(r"key:\s*'([^']+)'", content)
        key = key_match.group(1) if key_match else "unknown"

        data_match = re.search(r'data:\s*(\[.*)', content, re.DOTALL)
        if data_match:
            data_str = data_match.group(1).strip()
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(data_str)
            blobs.append({"key": key, "data": data})
    return blobs


def _safe_get(obj: Any, *indices, default=None):
    """Safely navigate nested lists/dicts."""
    current = obj
    for idx in indices:
        try:
            if current is None:
                return default
            current = current[idx]
        except (IndexError, KeyError, TypeError):
            return default
    return current if current is not None else default


def _proto_ts_to_datetime(ts_field: list | None) -> datetime.datetime | None:
    """Convert protobuf Timestamp [seconds, nanos] to datetime."""
    if not ts_field or not isinstance(ts_field, list) or len(ts_field) < 1:
        return None
    try:
        return datetime.datetime.fromtimestamp(ts_field[0])
    except (OSError, ValueError, TypeError):
        return None


def _html_to_text(html_str: str) -> str:
    """Strip HTML tags for plain text display."""
    if not html_str:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', html_str)
    text = re.sub(r'<li>', '  - ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('\xa0', ' ')
    return text.strip()


def _slugify(title: str) -> str:
    """Convert job title to URL slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-{2,}', '-', slug)
    return slug.strip('-')


def _split_qualifications(qual_html: str) -> tuple[str, str]:
    """Split combined qualifications HTML into (min, preferred)."""
    if not qual_html:
        return ("", "")
    parts = re.split(r'<h3>Preferred qualifications?:</h3>', qual_html, flags=re.IGNORECASE)
    min_html = re.sub(r'<h3>Minimum qualifications?:</h3>', '', parts[0]).strip()
    pref_html = parts[1].strip() if len(parts) > 1 else ""
    return (min_html, pref_html)


def _build_detail_url(job_id: str, title: str) -> str:
    """Build the public job detail page URL."""
    slug = _slugify(title)
    return f"{BASE_DETAIL_URL}/{job_id}-{slug}"


# ---------------------------------------------------------------------------
# Parse Companies (ds:0)
# ---------------------------------------------------------------------------

def parse_companies(ds0_data: list) -> list[dict]:
    """Parse ds:0 company/organization list."""
    companies = []
    for entry in _safe_get(ds0_data, 0, default=[]):
        company = {
            "resource_id": _safe_get(entry, 0, default=""),
            "display_name": _safe_get(entry, 1, default=""),
            "slug": _safe_get(entry, 2, default=""),
            "website_url": _safe_get(entry, 3, default=""),
            "careers_url": _safe_get(entry, 4, default=""),
            "logo_url": _safe_get(entry, 5, default=""),
        }
        companies.append(company)
    return companies


# ---------------------------------------------------------------------------
# Parse Jobs (ds:1)
# ---------------------------------------------------------------------------

def parse_jobs(ds1_data: list) -> tuple[list[dict], int, int]:
    """Parse ds:1 job listings.

    Returns: (jobs_list, total_results, page_size)
    """
    job_entries = _safe_get(ds1_data, 0, default=[])
    total_results = _safe_get(ds1_data, 2, default=0)
    page_size = _safe_get(ds1_data, 3, default=0)

    jobs = []
    for entry in job_entries:
        # Extract and split qualifications
        combined_qual = _safe_get(entry, 4, 1, default="")
        min_qual_html, pref_qual_html = _split_qualifications(combined_qual)

        # Parse locations
        locations = []
        for loc_entry in _safe_get(entry, 9, default=[]):
            locations.append({
                "display_name": _safe_get(loc_entry, 0, default=""),
                "addresses": _safe_get(loc_entry, 1, default=[]),
                "city": _safe_get(loc_entry, 2, default=""),
                "postal_code": _safe_get(loc_entry, 3, default=""),
                "state_region": _safe_get(loc_entry, 4, default=""),
                "country_code": _safe_get(loc_entry, 5, default=""),
            })

        job = {
            "job_id": _safe_get(entry, 0, default=""),
            "title": _safe_get(entry, 1, default=""),
            "apply_url": _safe_get(entry, 2, default=""),
            "responsibilities_html": _safe_get(entry, 3, 1, default=""),
            "qualifications_combined_html": combined_qual,
            "min_qualifications_html": min_qual_html,
            "preferred_qualifications_html": pref_qual_html,
            "min_qualifications_standalone_html": _safe_get(entry, 19, 1, default=""),
            "company_id": _safe_get(entry, 5, default=""),
            "company_name": _safe_get(entry, 7, default=""),
            "language_code": _safe_get(entry, 8, default=""),
            "locations": locations,
            "description_html": _safe_get(entry, 10, 1, default=""),
            "category_ids": _safe_get(entry, 11, default=[]),
            "created_at": _proto_ts_to_datetime(_safe_get(entry, 12)),
            "updated_at": _proto_ts_to_datetime(_safe_get(entry, 13)),
            "published_at": _proto_ts_to_datetime(_safe_get(entry, 14)),
            "benefits_html": _safe_get(entry, 15, 1, default=""),
            "additional_info_html": _safe_get(entry, 18, 1, default=""),
            "experience_level": _safe_get(entry, 20, default=0),
            "detail_url": _build_detail_url(
                _safe_get(entry, 0, default=""),
                _safe_get(entry, 1, default=""),
            ),
        }
        jobs.append(job)

    return jobs, total_results, page_size


# ---------------------------------------------------------------------------
# Display Functions
# ---------------------------------------------------------------------------

def print_section(title: str, char: str = "="):
    width = 100
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}")


def print_companies_table(companies: list[dict]):
    print_section("DS:0 -- COMPANIES / ORGANIZATIONS")
    print(f"{'#':>3}  {'Name':<25} {'Slug':<25} {'Resource UUID':<40}")
    print(f"{'---':>3}  {'---':<25} {'---':<25} {'---':<40}")
    for i, c in enumerate(companies):
        uuid = c["resource_id"].split("/")[-1] if "/" in c["resource_id"] else c["resource_id"]
        print(f"{i:3d}  {c['display_name']:<25} {c['slug']:<25} {uuid:<40}")
        if c["website_url"]:
            print(f"     Website: {c['website_url']}")
        if c["careers_url"]:
            print(f"     Careers: {c['careers_url']}")
        if c["logo_url"]:
            print(f"     Logo:    {c['logo_url'][:80]}...")


def print_jobs_table(jobs: list[dict]):
    print_section("DS:1 -- JOB LISTINGS TABLE")
    header = (
        f"{'#':>3}  "
        f"{'Job ID':<20} "
        f"{'Title':<55} "
        f"{'Location(s)':<30} "
        f"{'Exp':>5} "
        f"{'Cats':>8} "
        f"{'Posted':<12}"
    )
    print(header)
    print("-" * len(header))
    for i, job in enumerate(jobs):
        title = job["title"][:53] + ".." if len(job["title"]) > 55 else job["title"]
        locs = "; ".join(loc["display_name"] for loc in job["locations"])
        if len(locs) > 28:
            locs = locs[:26] + ".."
        exp = EXPERIENCE_LEVEL_MAP.get(job["experience_level"], f"?{job['experience_level']}")
        cats = ",".join(str(c) for c in job["category_ids"])
        posted = job["created_at"].strftime("%Y-%m-%d") if job["created_at"] else "N/A"
        print(
            f"{i:3d}  "
            f"{job['job_id']:<20} "
            f"{title:<55} "
            f"{locs:<30} "
            f"{exp:>5} "
            f"{cats:>8} "
            f"{posted:<12}"
        )


def print_field_mapping():
    print_section("COMPLETE FIELD INDEX MAPPING")
    mapping = [
        ("[0]", "job_id", "str", "Numeric job ID"),
        ("[1]", "title", "str", "Full job title"),
        ("[2]", "apply_url", "str", "Direct sign-in/apply URL with jobId param"),
        ("[3]", "responsibilities_html", "[None, str]", "Job responsibilities as HTML <ul>/<li>"),
        ("[4]", "qualifications_html", "[None, str]", "Combined min + preferred qualifications (with <h3> headers)"),
        ("[5]", "company_id", "str", "Cloud Talent Solution company resource path"),
        ("[6]", "(reserved)", "None", "Always None"),
        ("[7]", "company_name", "str", "Company display name (Google, DeepMind, etc.)"),
        ("[8]", "language_code", "str", "Locale (en-US)"),
        ("[9]", "locations", "list[list]", "Array of [display, [addrs], city, zip, state, country]"),
        ("[10]", "description_html", "[None, str]", "Full job description/overview as HTML"),
        ("[11]", "category_ids", "list[int]", "Job category codes: 2=SWE, 3=TechInfra, 4=DataSci"),
        ("[12]", "created_at", "[sec, ns]", "Protobuf Timestamp -- original post date"),
        ("[13]", "updated_at", "[sec, ns]", "Protobuf Timestamp -- last modified"),
        ("[14]", "published_at", "[sec, ns]", "Protobuf Timestamp -- publish time (~= updated_at)"),
        ("[15]", "benefits_html", "[None, str]", "Benefits/compensation (US roles) or empty"),
        ("[16]", "(reserved)", "None", "Always None"),
        ("[17]", "(reserved)", "None", "Always None"),
        ("[18]", "additional_info_html", "[None, str]", "Location pref note or empty"),
        ("[19]", "min_qualifications_html", "[None, str]", "Min qualifications ONLY (no headers, subset of [4])"),
        ("[20]", "experience_level", "int", "1=Entry, 2=Mid, 3=Advanced, 4=Director"),
    ]
    print(f"{'Index':<8} {'Field Name':<28} {'Type':<14} {'Description'}")
    print(f"{'-----':<8} {'----------':<28} {'----':<14} {'-----------'}")
    for idx, name, typ, desc in mapping:
        print(f"{idx:<8} {name:<28} {typ:<14} {desc}")


def print_job_detail(job: dict, index: int):
    """Print full detail for a single job."""
    print(f"\n{'~' * 100}")
    print(f" JOB {index}: {job['title']}")
    print(f"{'~' * 100}")
    print(f"  Job ID:           {job['job_id']}")
    print(f"  Company:          {job['company_name']}")
    print(f"  Experience:       {EXPERIENCE_LEVEL_MAP.get(job['experience_level'], '?')} (code={job['experience_level']})")
    print(f"  Categories:       {[CATEGORY_MAP.get(c, f'?{c}') for c in job['category_ids']]}")
    print(f"  Language:         {job['language_code']}")
    print(f"  Detail URL:       {job['detail_url']}")
    print(f"  Apply URL:        {job['apply_url'][:100]}...")
    print(f"  Created:          {job['created_at']}")
    print(f"  Updated:          {job['updated_at']}")
    print(f"  Published:        {job['published_at']}")

    print(f"\n  LOCATIONS ({len(job['locations'])}):")
    for loc in job["locations"]:
        addr = loc["addresses"][0] if loc["addresses"] else "N/A"
        print(f"    - {loc['display_name']}")
        print(f"      Address: {addr}")
        print(f"      City={loc['city']}, ZIP={loc['postal_code']}, State={loc['state_region']}, Country={loc['country_code']}")

    desc_text = _html_to_text(job["description_html"])
    print(f"\n  DESCRIPTION (first 300 chars):")
    print(f"    {desc_text[:300]}...")

    resp_text = _html_to_text(job["responsibilities_html"])
    print(f"\n  RESPONSIBILITIES:")
    print(f"    {resp_text[:400]}")

    min_text = _html_to_text(job["min_qualifications_standalone_html"])
    print(f"\n  MINIMUM QUALIFICATIONS:")
    print(f"    {min_text[:400]}")

    pref_text = _html_to_text(job["preferred_qualifications_html"])
    if pref_text:
        print(f"\n  PREFERRED QUALIFICATIONS:")
        print(f"    {pref_text[:400]}")

    if job["benefits_html"]:
        ben_text = _html_to_text(job["benefits_html"])
        print(f"\n  BENEFITS (first 200 chars):")
        print(f"    {ben_text[:200]}...")

    if job["additional_info_html"]:
        info_text = _html_to_text(job["additional_info_html"])
        print(f"\n  ADDITIONAL INFO:")
        print(f"    {info_text}")


def print_stats(jobs: list[dict], total_results: int, page_size: int, dom_count: int):
    print_section("STATISTICS")

    # Basic counts
    print(f"  AF blob jobs (this page):  {len(jobs)}")
    print(f"  DOM-extracted jobs:        {dom_count}")
    print(f"  Total results (all pages): {total_results}")
    print(f"  Page size:                 {page_size}")
    print(f"  Estimated total pages:     {(total_results + page_size - 1) // page_size}")

    # Unique locations
    all_locs = set()
    all_cities = set()
    all_countries = set()
    for job in jobs:
        for loc in job["locations"]:
            all_locs.add(loc["display_name"])
            all_cities.add(loc["city"])
            all_countries.add(loc["country_code"])

    print(f"\n  Unique display locations:  {len(all_locs)}")
    for loc in sorted(all_locs):
        print(f"    - {loc}")

    print(f"\n  Unique cities:             {len(all_cities)}")
    for city in sorted(all_cities):
        print(f"    - {city}")

    print(f"\n  Unique countries:          {len(all_countries)}")
    for cc in sorted(all_countries):
        print(f"    - {cc}")

    # Companies
    companies = set(job["company_name"] for job in jobs)
    print(f"\n  Unique companies:          {len(companies)}")
    for c in sorted(companies):
        count = sum(1 for j in jobs if j["company_name"] == c)
        print(f"    - {c} ({count} jobs)")

    # Experience levels
    print(f"\n  Experience level distribution:")
    exp_counts: dict[int, int] = {}
    for job in jobs:
        exp_counts[job["experience_level"]] = exp_counts.get(job["experience_level"], 0) + 1
    for code in sorted(exp_counts):
        label = EXPERIENCE_LEVEL_MAP.get(code, f"Unknown({code})")
        print(f"    - {label} (code={code}): {exp_counts[code]} jobs")

    # Category distribution
    print(f"\n  Category code distribution:")
    cat_counts: dict[int, int] = {}
    for job in jobs:
        for cat in job["category_ids"]:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for code in sorted(cat_counts):
        label = CATEGORY_MAP.get(code, f"Unknown({code})")
        print(f"    - {label} (code={code}): {cat_counts[code]} jobs")

    # Multi-location jobs
    multi_loc = [j for j in jobs if len(j["locations"]) > 1]
    print(f"\n  Multi-location jobs:       {len(multi_loc)}")
    for j in multi_loc:
        locs = ", ".join(loc["display_name"] for loc in j["locations"])
        print(f"    - {j['title'][:50]}: {locs}")

    # Jobs with benefits
    with_benefits = sum(1 for j in jobs if j["benefits_html"])
    print(f"\n  Jobs with benefits info:   {with_benefits}")

    # Jobs with additional info
    with_info = sum(1 for j in jobs if j["additional_info_html"])
    print(f"  Jobs with additional info: {with_info}")

    # Date range
    dates = [j["created_at"] for j in jobs if j["created_at"]]
    if dates:
        print(f"\n  Posting date range:        {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}")

    # Average qualifications length
    avg_min = sum(len(j["min_qualifications_standalone_html"]) for j in jobs) / len(jobs) if jobs else 0
    avg_pref = sum(len(j["preferred_qualifications_html"]) for j in jobs) / len(jobs) if jobs else 0
    avg_resp = sum(len(j["responsibilities_html"]) for j in jobs) / len(jobs) if jobs else 0
    avg_desc = sum(len(j["description_html"]) for j in jobs) / len(jobs) if jobs else 0
    print(f"\n  Avg HTML field lengths:")
    print(f"    - Min qualifications:    {avg_min:.0f} chars")
    print(f"    - Pref qualifications:   {avg_pref:.0f} chars")
    print(f"    - Responsibilities:      {avg_resp:.0f} chars")
    print(f"    - Description:           {avg_desc:.0f} chars")


def print_raw_entry_dump(ds1_data: list, index: int = 0):
    """Dump raw field values for a single job entry (for debugging)."""
    print_section(f"RAW FIELD DUMP -- JOB ENTRY [{index}]")
    entry = ds1_data[0][index]
    for i, field in enumerate(entry):
        if field is None:
            print(f"  [{i:2d}]: None")
        elif isinstance(field, list):
            flat = json.dumps(field, ensure_ascii=False)
            if len(flat) > 120:
                print(f"  [{i:2d}]: list[{len(field)}] = {flat[:120]}...")
            else:
                print(f"  [{i:2d}]: list[{len(field)}] = {flat}")
        elif isinstance(field, str):
            if len(field) > 100:
                print(f"  [{i:2d}]: str({len(field)}) = {field[:100]}...")
            else:
                print(f"  [{i:2d}]: str = {field!r}")
        elif isinstance(field, (int, float)):
            print(f"  [{i:2d}]: {type(field).__name__} = {field}")
        else:
            print(f"  [{i:2d}]: {type(field).__name__} = {repr(field)[:100]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    html_path = Path(__file__).parent / "jobs_page.html"
    json_path = Path(__file__).parent / "jobs_data.json"

    if not html_path.exists():
        print(f"ERROR: {html_path} not found.")
        sys.exit(1)

    print(f"Loading {html_path.name} ({html_path.stat().st_size:,} bytes)...")
    html = html_path.read_text(encoding="utf-8")

    # -----------------------------------------------------------------------
    # Extract AF_initDataCallback blobs
    # -----------------------------------------------------------------------
    print("\n--- Extracting AF_initDataCallback blobs ---")
    blobs = _extract_af_init_data(html)
    if not blobs:
        print("FAIL: No AF_initDataCallback blobs found!")
        sys.exit(1)

    for b in blobs:
        data = b["data"]
        data_type = type(data).__name__
        data_preview = json.dumps(data, ensure_ascii=False)[:80] if data else "None"
        print(f"  {b['key']}: type={data_type}, preview={data_preview}...")
    print(f"  Total: {len(blobs)} blobs")

    # Identify ds:0 and ds:1
    ds0_data = None
    ds1_data = None
    for b in blobs:
        if b["key"] == "ds:0":
            ds0_data = b["data"]
        elif b["key"] == "ds:1":
            ds1_data = b["data"]

    if not ds1_data:
        print("FAIL: ds:1 blob not found!")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # DS:1 Top-level structure
    # -----------------------------------------------------------------------
    print_section("DS:1 TOP-LEVEL STRUCTURE")
    print(f"  ds1 type: {type(ds1_data).__name__}, length: {len(ds1_data)}")
    for i, item in enumerate(ds1_data):
        if item is None:
            print(f"  ds1[{i}]: None")
        elif isinstance(item, list):
            print(f"  ds1[{i}]: list, length={len(item)}")
        elif isinstance(item, (int, float)):
            print(f"  ds1[{i}]: {type(item).__name__}, value={item}")
        else:
            print(f"  ds1[{i}]: {type(item).__name__}")

    # -----------------------------------------------------------------------
    # Parse companies
    # -----------------------------------------------------------------------
    if ds0_data:
        companies = parse_companies(ds0_data)
        print_companies_table(companies)

    # -----------------------------------------------------------------------
    # Parse jobs
    # -----------------------------------------------------------------------
    jobs, total_results, page_size = parse_jobs(ds1_data)

    # Raw dump of first entry
    print_raw_entry_dump(ds1_data, index=0)

    # Field mapping reference
    print_field_mapping()

    # Jobs table
    print_jobs_table(jobs)

    # Full detail for first 3 jobs
    print_section("DETAILED JOB LISTINGS (first 3)")
    for i in range(min(3, len(jobs))):
        print_job_detail(jobs[i], i)

    # -----------------------------------------------------------------------
    # DOM comparison
    # -----------------------------------------------------------------------
    dom_count = 0
    if json_path.exists():
        with open(json_path) as f:
            json_data = json.load(f)
        dom_jobs = json_data.get("dom_extraction", {}).get("jobs", [])
        # Filter out non-job entries (like "Locations" from aria_fallback)
        dom_jobs = [j for j in dom_jobs if j.get("source") == "h3_fallback"]
        dom_count = len(dom_jobs)

        print_section("DOM vs AF_initDataCallback COMPARISON")
        print(f"  DOM h3_fallback jobs:  {dom_count}")
        print(f"  AF blob jobs:          {len(jobs)}")
        print(f"  Match:                 {'YES' if dom_count == len(jobs) else 'NO -- MISMATCH'}")

        # Compare titles
        print(f"\n  Title comparison:")
        for i, (af_job, dom_job) in enumerate(zip(jobs, dom_jobs)):
            match = af_job["title"] == dom_job["title"]
            status = "OK" if match else "MISMATCH"
            print(f"    [{i:2d}] {status}: AF={af_job['title'][:50]} | DOM={dom_job['title'][:50]}")

        # Show what AF provides that DOM does NOT
        print(f"\n  FIELDS AVAILABLE IN AF BLOB BUT NOT IN DOM:")
        af_fields = [
            "job_id", "apply_url", "description_html", "responsibilities_html",
            "min_qualifications_html", "preferred_qualifications_html",
            "company_id", "company_name", "locations (structured)",
            "category_ids", "created_at", "updated_at", "published_at",
            "benefits_html", "additional_info_html", "experience_level",
            "detail_url (constructed)", "language_code",
        ]
        for field in af_fields:
            print(f"    + {field}")
    else:
        dom_count = 20  # Fallback estimate

    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------
    print_stats(jobs, total_results, page_size, dom_count)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print_section("SUMMARY", "=")
    print(f"""
  The AF_initDataCallback ds:1 blob contains COMPLETE job listing data:
  - {len(jobs)} jobs on this page, {total_results} total across all pages
  - Each job has 21 fields including structured locations, HTML descriptions,
    qualifications (min + preferred), responsibilities, benefits, timestamps
  - Experience level enum: 1=Entry, 2=Mid, 3=Advanced, 4=Director
  - Category codes: {{2, 3, 4}} observed (likely SWE, TechInfra, DataSci)
  - Timestamps are protobuf format: [epoch_seconds, nanoseconds]
  - Detail URL: /jobs/results/{{job_id}}-{{title_slug}}
  - Pagination: page=N param, 20 results per page, total={total_results}

  ds:0 contains the company/org list with {len(companies) if ds0_data else 0} entries:
    {', '.join(c['display_name'] for c in companies) if ds0_data else 'N/A'}

  This is 10x richer than DOM scraping (which only gets title, no links).
""")


if __name__ == "__main__":
    main()
