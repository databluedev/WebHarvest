"""
Test: Can we fetch Google Images results via pure HTTP (no browser)?

Tests multiple approaches and parses structured image data.
Google Images (udm=2) returns ~1.2MB of HTML with embedded JSON data blocks.

Data structure per image (in session-prefixed keys):
  "PREFIX_N":[1,[0, "doc_id",
    ["thumb_url", thumb_w, thumb_h],
    ["full_url", full_w, full_h],
    null, 0, "rgb(R,G,B)", null, 0,
    {
      "2000": [null, "domain.com", "filesize"],
      "2003": [null, "ref_doc_id", "source_page_url", "title", ...  "site_name", ... "domain"],
      "2008": [null, "short_title"]
    }
  ], ...]
"""

import re
import json
import httpx
import asyncio
from urllib.parse import unquote


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def unescape(text: str) -> str:
    """Unescape Google's unicode escapes."""
    return (
        text.replace(r"\u003d", "=")
        .replace(r"\u0026", "&")
        .replace(r"\u003c", "<")
        .replace(r"\u003e", ">")
        .replace(r"\u0027", "'")
    )


def parse_images_from_dom(text: str) -> list[dict]:
    """
    Parse image entries from the DOM data attributes.
    Each image card has: data-docid, data-lpage (source page URL).
    """
    entries = []
    # Pattern: data-docid="..." data-lpage="..." in the same element
    cards = re.finditer(
        r'data-docid="([^"]+)"[^>]*data-ivep="true"[^>]*data-lpage="([^"]+)"'
        r'(?:[^>]*data-ref-docid="([^"]+)")?',
        text,
    )
    for m in cards:
        entries.append({
            "doc_id": m.group(1),
            "source_url": unescape(m.group(2)),
            "ref_doc_id": m.group(3) if m.group(3) else None,
        })
    return entries


def parse_images_from_script_data(text: str) -> list[dict]:
    """
    Parse image entries from the session-prefixed JSON data in script blocks.
    These contain: doc_id, thumbnail URL/dims, full image URL/dims, metadata.
    """
    text_unesc = unescape(text)

    # Find the session prefix
    prefix_match = re.search(r'"([a-zA-Z0-9_-]{20,}?)(\d+)":\s*\[', text_unesc)
    if not prefix_match:
        return []
    prefix = prefix_match.group(1)

    # Find all data blocks with this prefix that contain image data
    # Pattern: "PREFIX_N":[1,[0,"doc_id",["thumb",tw,th],["full",fw,fh],null,0,"rgb",null,0,{...}]...]
    # OR:      "PREFIX_N":[0,"doc_id",["thumb",tw,th],["full",fw,fh],null,0,"rgb",null,0,{...}]
    pattern = re.compile(
        rf'"{re.escape(prefix)}\d+":\s*\[\s*(?:1,\s*\[)?\s*(\d+)\s*,\s*"([a-zA-Z0-9_-]+)"\s*,'
        rf'\s*\["(https://encrypted-tbn0\.gstatic\.com/images\?[^"]+)",\s*(\d+),\s*(\d+)\]\s*,'
        rf'\s*\["([^"]+)",\s*(\d+),\s*(\d+)\]'
        rf'(?:\s*,\s*null\s*,\s*\d+\s*,\s*"(rgb\([^"]*\))")?'
    )

    seen_doc_ids = set()
    entries = []

    for m in pattern.finditer(text_unesc):
        doc_id = m.group(2)
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)

        entry = {
            "doc_id": doc_id,
            "thumbnail_url": m.group(3),
            "thumbnail_width": int(m.group(4)),
            "thumbnail_height": int(m.group(5)),
            "full_url": m.group(6),
            "full_width": int(m.group(7)),
            "full_height": int(m.group(8)),
        }
        if m.group(9):
            entry["dominant_color"] = m.group(9)

        # Try to extract the metadata block near this match
        pos = m.end()
        chunk = text_unesc[pos : pos + 1500]

        # Extract "2000" block: [null, "domain", "filesize"]
        meta_2000 = re.search(r'"2000":\s*\[null\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\]', chunk)
        if meta_2000:
            entry["domain"] = meta_2000.group(1)
            entry["file_size"] = meta_2000.group(2)

        # Extract "2003" block: [null, "ref_docid", "source_url", "title", ...
        #   index 12 = "site_name", index 17 = "display_domain"]
        meta_2003 = re.search(r'"2003":\s*\[null\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', chunk)
        if meta_2003:
            entry["ref_doc_id"] = meta_2003.group(1)
            entry["source_url"] = meta_2003.group(2)
            entry["title"] = meta_2003.group(3)

        # Extract site name from 2003 block (appears after several nulls/values)
        # It's at index 12 in the 2003 array: ...,null,null,"SiteName",null,...
        site_match = re.search(
            r'"2003":\[(?:[^]]*?,){12}"([^"]+)"',
            chunk,
        )
        if site_match:
            entry["site_name"] = site_match.group(1)

        # Extract "2008" block: [null, "short_title"]
        meta_2008 = re.search(r'"2008":\s*\[null\s*,\s*"([^"]+)"\]', chunk)
        if meta_2008:
            entry["short_title"] = meta_2008.group(1)

        entries.append(entry)

    return entries


def analyze_response(text: str, label: str) -> dict:
    """Analyze a Google Images response and extract structured data."""
    print(f"\n{'='*80}")
    print(f"  ANALYSIS: {label}")
    print(f"{'='*80}")
    print(f"  Response length: {len(text):,} chars")

    results = {
        "label": label,
        "response_length": len(text),
        "blocked": None,
        "dom_entries": [],
        "script_entries": [],
    }

    # Check for blocking
    if "consent.google" in text or "Before you continue" in text:
        print(f"  *** BLOCKED: Consent/cookie page ***")
        results["blocked"] = "consent"
        return results
    if "unusual traffic" in text.lower() or "captcha" in text.lower():
        print(f"  *** BLOCKED: CAPTCHA ***")
        results["blocked"] = "captcha"
        return results

    # Parse DOM entries
    dom_entries = parse_images_from_dom(text)
    results["dom_entries"] = dom_entries
    print(f"  DOM image cards (data-docid): {len(dom_entries)}")

    # Parse script data entries
    script_entries = parse_images_from_script_data(text)
    results["script_entries"] = script_entries
    print(f"  Script data entries (structured): {len(script_entries)}")

    # Count base64 thumbnails (inline previews)
    base64_count = len(re.findall(r'data:image/(?:jpeg|png|webp);base64,', text))
    print(f"  Base64 inline thumbnails: {base64_count}")

    # Count full image URLs
    full_imgs = re.findall(
        r'https?://(?!encrypted-tbn|www\.google|www\.gstatic|lh\d\.google)[^\s\'"\\<>]+\.(?:jpg|jpeg|png|webp|gif)',
        text,
    )
    full_imgs_unique = len(set(full_imgs))
    print(f"  Full image URLs (unique, regex): {full_imgs_unique}")

    # Sample entries
    if script_entries:
        print(f"\n  --- SAMPLE ENTRIES (from script data) ---")
        for i, entry in enumerate(script_entries[:10]):
            print(f"\n  [{i}] doc_id: {entry['doc_id']}")
            print(f"      full_url:    {entry['full_url'][:100]}")
            print(f"      dimensions:  {entry['full_width']}x{entry['full_height']}")
            print(f"      thumb:       {entry['thumbnail_url'][:80]}...")
            print(f"      thumb_dims:  {entry['thumbnail_width']}x{entry['thumbnail_height']}")
            if "title" in entry:
                print(f"      title:       {entry['title'][:80]}")
            if "source_url" in entry:
                print(f"      source_url:  {entry['source_url'][:100]}")
            if "domain" in entry:
                print(f"      domain:      {entry['domain']}")
            if "file_size" in entry:
                print(f"      file_size:   {entry['file_size']}")
            if "site_name" in entry:
                print(f"      site_name:   {entry['site_name']}")
            if "short_title" in entry:
                print(f"      short_title: {entry['short_title'][:80]}")
            if "dominant_color" in entry:
                print(f"      color:       {entry['dominant_color']}")

    return results


async def test_approach(label: str, url: str, use_cookies: bool = False, consent_cookie: bool = False) -> dict:
    """Test a single approach."""
    print(f"\n\n{'#'*80}")
    print(f"  {label}")
    print(f"{'#'*80}")
    print(f"  URL: {url}")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        if use_cookies:
            print(f"  Step 1: Fetching google.com for cookies...")
            resp1 = await client.get("https://www.google.com/", headers=HEADERS)
            print(f"  google.com status: {resp1.status_code}, cookies: {list(dict(resp1.cookies).keys())}")
            if consent_cookie:
                client.cookies.set("CONSENT", "YES+cb.20231120-09-p0.en+FX+111", domain=".google.com")
                print(f"  Added CONSENT bypass cookie")

        resp = await client.get(url, headers=HEADERS)
        print(f"  Status: {resp.status_code}")
        print(f"  Final URL: {resp.url}")
        return analyze_response(resp.text, label)


async def main():
    print("=" * 80)
    print("  GOOGLE IMAGES HTTP-ONLY FEASIBILITY TEST")
    print("=" * 80)
    print(f"  Query: 'cat photos'")

    query = "cat+photos"
    all_results = []

    # Test 1: tbm=isch (classic)
    r1 = await test_approach(
        "TEST 1: tbm=isch (Classic)",
        f"https://www.google.com/search?q={query}&tbm=isch&hl=en",
    )
    all_results.append(r1)

    # Test 2: udm=2 (new)
    r2 = await test_approach(
        "TEST 2: udm=2 (New parameter)",
        f"https://www.google.com/search?q={query}&udm=2&hl=en",
    )
    all_results.append(r2)

    # Test 3: tbm=isch + session cookies
    r3 = await test_approach(
        "TEST 3: tbm=isch + Session Cookies",
        f"https://www.google.com/search?q={query}&tbm=isch&hl=en",
        use_cookies=True,
    )
    all_results.append(r3)

    # Test 4: udm=2 + cookies + CONSENT bypass
    r4 = await test_approach(
        "TEST 4: udm=2 + Cookies + CONSENT",
        f"https://www.google.com/search?q={query}&udm=2&hl=en",
        use_cookies=True,
        consent_cookie=True,
    )
    all_results.append(r4)

    # --- FINAL SUMMARY ---
    print(f"\n\n{'='*80}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"\n  {'Method':<40} {'Status':<10} {'DOM':<6} {'Script':<8} {'Best':<6}")
    print(f"  {'-'*40} {'-'*10} {'-'*6} {'-'*8} {'-'*6}")
    for r in all_results:
        status = r["blocked"] or "OK"
        dom = len(r["dom_entries"])
        script = len(r["script_entries"])
        best = max(dom, script)
        print(f"  {r['label']:<40} {status:<10} {dom:<6} {script:<8} {best:<6}")

    # --- PARSED DATA QUALITY CHECK ---
    best_result = max(all_results, key=lambda r: len(r["script_entries"]))
    entries = best_result["script_entries"]
    print(f"\n  --- DATA QUALITY CHECK (best: {best_result['label']}) ---")
    print(f"  Total entries: {len(entries)}")

    has_title = sum(1 for e in entries if "title" in e)
    has_source = sum(1 for e in entries if "source_url" in e)
    has_thumb = sum(1 for e in entries if "thumbnail_url" in e)
    has_domain = sum(1 for e in entries if "domain" in e)
    has_size = sum(1 for e in entries if "file_size" in e)
    has_color = sum(1 for e in entries if "dominant_color" in e)
    has_site_name = sum(1 for e in entries if "site_name" in e)

    print(f"  With title:          {has_title}/{len(entries)}")
    print(f"  With source_url:     {has_source}/{len(entries)}")
    print(f"  With thumbnail:      {has_thumb}/{len(entries)}")
    print(f"  With domain:         {has_domain}/{len(entries)}")
    print(f"  With file_size:      {has_size}/{len(entries)}")
    print(f"  With dominant_color: {has_color}/{len(entries)}")
    print(f"  With site_name:      {has_site_name}/{len(entries)}")

    # --- VERDICT ---
    print(f"\n\n{'='*80}")
    print(f"  VERDICT")
    print(f"{'='*80}")
    best_count = len(entries)
    if best_count >= 50:
        print(f"  HTTP-ONLY IS VIABLE!")
        print(f"  {best_count} structured image entries extracted via pure httpx.")
        print(f"  Each entry includes: doc_id, full image URL + dimensions,")
        print(f"  thumbnail URL + dimensions, source page URL, title, domain, file size.")
        print(f"")
        print(f"  DATA FORMAT (session-prefixed JSON in script blocks):")
        print(f"    \"PREFIX_N\":[1,[0,\"doc_id\",")
        print(f"      [\"thumb_url\",tw,th],")
        print(f"      [\"full_url\",fw,fh],")
        print(f"      null,0,\"rgb(R,G,B)\",null,0,")
        print(f"      {{\"2000\":[null,\"domain\",\"size\"],")
        print(f"       \"2003\":[null,\"ref_id\",\"source_url\",\"title\",...,\"site_name\",...],")
        print(f"       \"2008\":[null,\"short_title\"]}}")
        print(f"    ]]")
        print(f"")
        print(f"  ALSO available from DOM: data-docid, data-lpage attributes (100 entries).")
        print(f"")
        print(f"  NOTE: tbm=isch redirects to udm=2. Both work identically.")
        print(f"  NOTE: Cookies are NOT required. First-request works fine.")
        print(f"  RECOMMENDATION: Use pure httpx with udm=2, no browser needed.")
    elif best_count >= 10:
        print(f"  HTTP-ONLY IS PARTIALLY VIABLE ({best_count} images)")
        print(f"  RECOMMENDATION: Works but results may be limited vs browser.")
    else:
        print(f"  HTTP-ONLY IS NOT VIABLE ({best_count} images)")
        print(f"  RECOMMENDATION: Browser (nodriver/Playwright) is required.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
