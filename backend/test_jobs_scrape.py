#!/usr/bin/env python3
"""
Standalone script to scrape Google Careers job listings using nodriver + Xvfb.
Extracts embedded data blobs, DOM job cards, and saves everything to JSON.
"""

import asyncio
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Xvfb (must start BEFORE importing nodriver so it picks up the virtual display)
# ---------------------------------------------------------------------------
from pyvirtualdisplay import Display

display = Display(visible=False, size=(1920, 1080))
display.start()
print(f"[+] Xvfb started on display :{display.display}")

import nodriver as uc  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_URL = (
    "https://www.google.com/about/careers/applications/jobs/results"
    "?q=software%20engineer&sort_by=relevance"
)
HTML_OUT = Path("/home/lostboi/aefoa/web-crawler/backend/jobs_page.html")
JSON_OUT = Path("/home/lostboi/aefoa/web-crawler/backend/jobs_data.json")

# Selectors to try when waiting for job listings to appear
JOB_SELECTORS = [
    ".lLd2Id",
    ".sMn82b",
    "[data-job-id]",
    "li.lLd2Id",
    "div[class*='job']",
    ".gc-card",
    "h3",
    "main",
]


def find_chrome_binary() -> str:
    """Find a usable Chromium / Chrome binary on the system."""
    for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome", "chrome"):
        path = shutil.which(name)
        if path:
            print(f"[+] Found browser binary: {path}")
            return path
    raise RuntimeError("No Chromium / Chrome binary found on PATH")


# ---------------------------------------------------------------------------
# Extraction helpers (run in Python after getting HTML)
# ---------------------------------------------------------------------------

def extract_af_init_data(html: str) -> list[dict]:
    """Extract AF_initDataCallback(...) payloads."""
    results = []
    # Pattern: AF_initDataCallback({key: '...', hash: '...', data: ...});
    pattern = re.compile(
        r"AF_initDataCallback\(\s*\{(.*?)\}\s*\)\s*;",
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        block = m.group(1)
        # Pull key
        key_m = re.search(r"""key\s*:\s*['"]([^'"]+)['"]""", block)
        hash_m = re.search(r"""hash\s*:\s*['"]([^'"]+)['"]""", block)
        data_m = re.search(r"data\s*:\s*(\[.*)", block, re.DOTALL)
        entry: dict = {
            "key": key_m.group(1) if key_m else None,
            "hash": hash_m.group(1) if hash_m else None,
        }
        if data_m:
            raw = data_m.group(1).rstrip().rstrip(",").rstrip()
            # Attempt JSON parse (may fail on trailing commas / JS literals)
            try:
                entry["data"] = json.loads(raw)
                entry["data_type"] = "parsed"
            except json.JSONDecodeError:
                entry["data_preview"] = raw[:2000]
                entry["data_type"] = "raw_preview"
                entry["data_length"] = len(raw)
        results.append(entry)
    return results


def extract_json_ld(html: str) -> list:
    """Extract <script type="application/ld+json"> blocks."""
    results = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        try:
            results.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            results.append({"raw_preview": m.group(1)[:2000]})
    return results


def extract_window_assignments(html: str) -> dict:
    """Extract window.__data, window._sharedData, or any window.* = {...large JSON...}."""
    results = {}
    pattern = re.compile(
        r"window\.(\w+)\s*=\s*(\{.{500,}?\})\s*;",
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        var_name = m.group(1)
        raw = m.group(2)
        try:
            results[var_name] = json.loads(raw)
        except json.JSONDecodeError:
            results[var_name] = {"raw_preview": raw[:2000], "length": len(raw)}
    return results


def extract_large_script_json(html: str) -> list[dict]:
    """Find large <script> blocks containing JSON arrays/objects with job keywords."""
    results = []
    job_keywords = re.compile(
        r"(software.engineer|job_id|jobId|job_title|jobTitle|location|requisition|posting)",
        re.IGNORECASE,
    )
    script_pattern = re.compile(
        r"<script(?:\s[^>]*)?>(.{1000,}?)</script>",
        re.DOTALL | re.IGNORECASE,
    )
    for m in script_pattern.finditer(html):
        body = m.group(1).strip()
        if not job_keywords.search(body):
            continue
        # Try to find the biggest JSON blob inside
        for json_m in re.finditer(r"(\[[\s\S]{500,}?\]|\{[\s\S]{500,}?\})", body):
            raw = json_m.group(1)
            try:
                parsed = json.loads(raw)
                results.append({"type": "parsed", "data": parsed})
            except json.JSONDecodeError:
                results.append({
                    "type": "raw_preview",
                    "preview": raw[:2000],
                    "length": len(raw),
                })
            if len(results) > 20:
                break
    return results


def extract_data_attributes(html: str) -> list[dict]:
    """Extract data-* attributes that contain JSON."""
    results = []
    pattern = re.compile(r'data-([\w-]+)=["\'](\{.{100,}?\}|\[.{100,}?\])["\']', re.DOTALL)
    for m in pattern.finditer(html):
        attr_name = m.group(1)
        raw = m.group(2)
        try:
            results.append({"attribute": attr_name, "data": json.loads(raw)})
        except json.JSONDecodeError:
            results.append({"attribute": attr_name, "raw_preview": raw[:1000]})
    return results


# ---------------------------------------------------------------------------
# JavaScript to run inside the browser for DOM extraction
# ---------------------------------------------------------------------------
JS_EXTRACT_JOBS = """
(() => {
    const jobs = [];

    // Strategy 1: .lLd2Id list items (Google Careers standard)
    document.querySelectorAll('li.lLd2Id').forEach(li => {
        const titleEl = li.querySelector('h3, .QJPWVe, [class*="title"]');
        const linkEl = li.querySelector('a[href*="jobs/results"]') || li.querySelector('a');
        const locEl = li.querySelector('.r0wTof, .pwO9Dc, [class*="location"]');
        const descEl = li.querySelector('.Xsxa1e, [class*="description"], [class*="snippet"]');
        const teamEl = li.querySelector('.wHhDY, [class*="company"], [class*="team"]');
        const jobId = li.getAttribute('data-job-id') || li.getAttribute('data-id') || '';
        jobs.push({
            source: 'li.lLd2Id',
            job_id: jobId,
            title: titleEl ? titleEl.textContent.trim() : '',
            link: linkEl ? linkEl.href : '',
            location: locEl ? locEl.textContent.trim() : '',
            team: teamEl ? teamEl.textContent.trim() : '',
            description: descEl ? descEl.textContent.trim().slice(0, 500) : '',
        });
    });

    // Strategy 2: [data-job-id] elements
    document.querySelectorAll('[data-job-id]').forEach(el => {
        const id = el.getAttribute('data-job-id');
        // Skip if already captured
        if (jobs.some(j => j.job_id === id)) return;
        const titleEl = el.querySelector('h3, [class*="title"]');
        const linkEl = el.querySelector('a');
        const locEl = el.querySelector('[class*="location"]');
        jobs.push({
            source: '[data-job-id]',
            job_id: id,
            title: titleEl ? titleEl.textContent.trim() : '',
            link: linkEl ? linkEl.href : '',
            location: locEl ? locEl.textContent.trim() : '',
        });
    });

    // Strategy 3: gc-card elements
    document.querySelectorAll('.gc-card').forEach(card => {
        const titleEl = card.querySelector('h3, h2, [class*="title"]');
        const linkEl = card.querySelector('a');
        const locEl = card.querySelector('[class*="location"]');
        jobs.push({
            source: '.gc-card',
            title: titleEl ? titleEl.textContent.trim() : '',
            link: linkEl ? linkEl.href : '',
            location: locEl ? locEl.textContent.trim() : '',
        });
    });

    // Strategy 4: any h3 inside main that looks like a job title
    if (jobs.length === 0) {
        document.querySelectorAll('main h3, [role="main"] h3').forEach(h3 => {
            const parent = h3.closest('a') || h3.parentElement;
            const linkEl = parent.tagName === 'A' ? parent : parent.querySelector('a');
            jobs.push({
                source: 'h3_fallback',
                title: h3.textContent.trim(),
                link: linkEl ? linkEl.href : '',
            });
        });
    }

    // Strategy 5: broad search — any element with role="listitem" or aria-label containing "job"
    document.querySelectorAll('[role="listitem"], [aria-label*="job" i], [aria-label*="Job" i]').forEach(el => {
        const titleEl = el.querySelector('h3, h2, [class*="title"]');
        if (!titleEl) return;
        const title = titleEl.textContent.trim();
        if (jobs.some(j => j.title === title)) return;
        const linkEl = el.querySelector('a');
        jobs.push({
            source: 'aria_fallback',
            title: title,
            link: linkEl ? linkEl.href : '',
        });
    });

    return JSON.stringify({
        job_count: jobs.length,
        jobs: jobs,
        page_title: document.title,
        current_url: location.href,
        body_text_length: document.body.innerText.length,
        all_h3: Array.from(document.querySelectorAll('h3')).map(e => e.textContent.trim()).slice(0, 30),
        all_links_count: document.querySelectorAll('a').length,
        main_text_preview: (document.querySelector('main') || document.body).innerText.slice(0, 3000),
    });
})()
"""

JS_EXTRACT_EMBEDDED_DATA = """
(() => {
    const result = {};

    // XHR/fetch intercepted data (if any was stored)
    if (window.__xhrData) result.xhrData = window.__xhrData;
    if (window.__fetchData) result.fetchData = window.__fetchData;

    // Check for common SPA data stores
    const candidates = [
        '__data', '_sharedData', '__NEXT_DATA__', '__NUXT__',
        '__APP_STATE__', '__INITIAL_STATE__', 'dataLayer',
        '__PRELOADED_STATE__', 'pageData', 'jobsData',
    ];
    for (const key of candidates) {
        if (window[key] && typeof window[key] === 'object') {
            try {
                result[key] = JSON.parse(JSON.stringify(window[key]));
            } catch(e) {
                result[key] = String(window[key]).slice(0, 2000);
            }
        }
    }

    // Google-specific: WIZ_global_data
    if (window.WIZ_global_data) {
        try {
            result.WIZ_global_data = JSON.parse(JSON.stringify(window.WIZ_global_data));
        } catch(e) {}
    }

    // Enumerate all window properties that are large objects
    const large = {};
    for (const key of Object.getOwnPropertyNames(window)) {
        try {
            const val = window[key];
            if (val && typeof val === 'object' && !Element.prototype.isPrototypeOf(val)) {
                const s = JSON.stringify(val);
                if (s && s.length > 1000) {
                    large[key] = { length: s.length, preview: s.slice(0, 500) };
                }
            }
        } catch(e) {}
    }
    result._large_window_objects = large;

    return JSON.stringify(result);
})()
"""


# ---------------------------------------------------------------------------
# Main async flow
# ---------------------------------------------------------------------------
async def main():
    chrome_path = find_chrome_binary()

    print(f"[+] Target URL: {TARGET_URL}")
    print("[+] Launching browser via nodriver ...")

    browser = await uc.start(
        browser_executable_path=chrome_path,
        sandbox=False,
        headless=False,  # nodriver needs a display (Xvfb provides it)
        browser_args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--window-size=1920,1080",
            "--lang=en-US",
        ],
    )

    print("[+] Browser launched, navigating to target URL ...")
    tab = await browser.get(TARGET_URL)

    # Wait for page to initially load
    print("[+] Waiting 10s for SPA to render ...")
    await asyncio.sleep(10)

    # Check current URL (might have redirected or shown consent)
    current_url = None
    try:
        current_url_result = await tab.evaluate("location.href")
        current_url = str(current_url_result)
        print(f"[+] Current URL: {current_url}")
    except Exception as e:
        print(f"[!] Could not get current URL: {e}")

    # Handle consent screen if present
    try:
        consent_result = await tab.evaluate("""
            (() => {
                // Google consent buttons
                const btns = document.querySelectorAll(
                    'button[aria-label*="Accept"], button[aria-label*="Agree"], ' +
                    'button[aria-label*="consent"], form[action*="consent"] button, ' +
                    '#L2AGLb, .tHlp8d'
                );
                if (btns.length > 0) {
                    btns[0].click();
                    return 'clicked_consent: ' + btns[0].textContent.trim();
                }
                return 'no_consent_screen';
            })()
        """)
        print(f"[+] Consent check: {consent_result}")
        if "clicked" in str(consent_result):
            print("[+] Waiting 5s after consent ...")
            await asyncio.sleep(5)
    except Exception as e:
        print(f"[!] Consent check error: {e}")

    # Try to find job listings with various selectors
    print("[+] Probing for job listing selectors ...")
    for sel in JOB_SELECTORS:
        try:
            count = await tab.evaluate(f"document.querySelectorAll('{sel}').length")
            print(f"    {sel} => {count} elements")
        except Exception as e:
            print(f"    {sel} => error: {e}")

    # Scroll down multiple times to trigger lazy loading
    print("[+] Scrolling to trigger lazy loading ...")
    for i in range(8):
        try:
            await tab.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await asyncio.sleep(1.5)
            scroll_y = await tab.evaluate("window.scrollY")
            doc_height = await tab.evaluate("document.documentElement.scrollHeight")
            print(f"    Scroll {i+1}/8: scrollY={scroll_y}, docHeight={doc_height}")
        except Exception as e:
            print(f"    Scroll {i+1}/8: error: {e}")

    # Scroll back to top
    try:
        await tab.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass
    await asyncio.sleep(2)

    # Re-check selectors after scrolling
    print("[+] Re-checking selectors after scroll ...")
    for sel in JOB_SELECTORS:
        try:
            count = await tab.evaluate(f"document.querySelectorAll('{sel}').length")
            if count and int(str(count)) > 0:
                print(f"    {sel} => {count} elements")
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Extract data via JavaScript in the browser
    # -----------------------------------------------------------------------
    print("[+] Extracting job listings from DOM via JS ...")
    dom_jobs_raw = None
    try:
        dom_jobs_raw = await tab.evaluate(JS_EXTRACT_JOBS)
        dom_jobs_raw = str(dom_jobs_raw)
    except Exception as e:
        print(f"[!] DOM extraction error: {e}")
        dom_jobs_raw = json.dumps({"error": str(e)})

    print("[+] Extracting embedded data from window objects ...")
    embedded_data_raw = None
    try:
        embedded_data_raw = await tab.evaluate(JS_EXTRACT_EMBEDDED_DATA)
        embedded_data_raw = str(embedded_data_raw)
    except Exception as e:
        print(f"[!] Embedded data extraction error: {e}")
        embedded_data_raw = json.dumps({"error": str(e)})

    # -----------------------------------------------------------------------
    # Get full rendered HTML
    # -----------------------------------------------------------------------
    print("[+] Capturing full rendered HTML ...")
    html = ""
    try:
        html = await tab.evaluate("document.documentElement.outerHTML")
        html = str(html)
    except Exception as e:
        print(f"[!] HTML capture error: {e}")

    # Close browser
    print("[+] Closing browser ...")
    try:
        browser.stop()
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Save HTML
    # -----------------------------------------------------------------------
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"[+] HTML saved to {HTML_OUT} ({len(html):,} bytes)")

    # -----------------------------------------------------------------------
    # Python-side extraction from HTML
    # -----------------------------------------------------------------------
    print("[+] Extracting AF_initDataCallback blobs ...")
    af_blobs = extract_af_init_data(html)
    print(f"    Found {len(af_blobs)} AF_initDataCallback entries")
    for blob in af_blobs:
        print(f"      key={blob.get('key')}, hash={blob.get('hash')}, type={blob.get('data_type')}")

    print("[+] Extracting JSON-LD ...")
    json_ld = extract_json_ld(html)
    print(f"    Found {len(json_ld)} JSON-LD blocks")

    print("[+] Extracting window.* assignments ...")
    window_data = extract_window_assignments(html)
    print(f"    Found {len(window_data)} window assignments")
    for k in window_data:
        print(f"      window.{k}")

    print("[+] Extracting large script JSON blobs ...")
    large_scripts = extract_large_script_json(html)
    print(f"    Found {len(large_scripts)} large script JSON blobs")

    print("[+] Extracting data-* attribute JSON ...")
    data_attrs = extract_data_attributes(html)
    print(f"    Found {len(data_attrs)} data-attribute JSON blobs")

    # Parse the JS-extracted results
    dom_jobs = {}
    try:
        dom_jobs = json.loads(dom_jobs_raw) if dom_jobs_raw else {}
    except json.JSONDecodeError:
        dom_jobs = {"raw": dom_jobs_raw[:3000] if dom_jobs_raw else ""}

    embedded_data = {}
    try:
        embedded_data = json.loads(embedded_data_raw) if embedded_data_raw else {}
    except json.JSONDecodeError:
        embedded_data = {"raw": embedded_data_raw[:3000] if embedded_data_raw else ""}

    # -----------------------------------------------------------------------
    # Compile final output
    # -----------------------------------------------------------------------
    output = {
        "metadata": {
            "url": TARGET_URL,
            "current_url": current_url,
            "html_size": len(html),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
        "dom_extraction": dom_jobs,
        "embedded_window_data": embedded_data,
        "af_init_data_callbacks": af_blobs,
        "json_ld": json_ld,
        "window_assignments": window_data,
        "large_script_json": large_scripts,
        "data_attributes": data_attrs,
    }

    JSON_OUT.write_text(json.dumps(output, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\n[+] Data saved to {JSON_OUT}")

    # -----------------------------------------------------------------------
    # Print stats
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STATS")
    print("=" * 70)
    print(f"  HTML size:                  {len(html):,} bytes")
    print(f"  Page title:                 {dom_jobs.get('page_title', 'N/A')}")
    print(f"  Current URL:                {current_url}")
    print(f"  DOM jobs found:             {dom_jobs.get('job_count', 0)}")
    print(f"  AF_initDataCallback blobs:  {len(af_blobs)}")
    print(f"  JSON-LD blocks:             {len(json_ld)}")
    print(f"  Window assignments:         {len(window_data)}")
    print(f"  Large script JSON:          {len(large_scripts)}")
    print(f"  Data-attribute JSON:         {len(data_attrs)}")

    # Sample job titles
    jobs_list = dom_jobs.get("jobs", [])
    if jobs_list:
        print(f"\n  Sample job titles ({min(10, len(jobs_list))} of {len(jobs_list)}):")
        for j in jobs_list[:10]:
            title = j.get("title", "???")
            loc = j.get("location", "")
            print(f"    - {title}  [{loc}]")
    else:
        print("\n  No DOM jobs extracted.")
        # Show h3 headings as fallback
        h3s = dom_jobs.get("all_h3", [])
        if h3s:
            print(f"  H3 headings found ({len(h3s)}):")
            for h in h3s[:15]:
                print(f"    - {h}")

    # Show main text preview
    preview = dom_jobs.get("main_text_preview", "")
    if preview:
        print(f"\n  Main text preview (first 1500 chars):")
        print("  " + preview[:1500].replace("\n", "\n  "))

    # AF blob keys
    if af_blobs:
        print(f"\n  AF_initDataCallback keys:")
        for blob in af_blobs:
            k = blob.get("key", "?")
            dt = blob.get("data_type", "?")
            dlen = blob.get("data_length", "?")
            print(f"    key={k}  type={dt}  length={dlen}")

    # Large window objects summary
    large_objs = embedded_data.get("_large_window_objects", {})
    if large_objs:
        print(f"\n  Large window objects ({len(large_objs)}):")
        # Sort by size descending
        sorted_objs = sorted(large_objs.items(), key=lambda x: x[1].get("length", 0), reverse=True)
        for name, info in sorted_objs[:15]:
            print(f"    window.{name}: {info.get('length', '?')} chars")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
    finally:
        display.stop()
        print("[+] Xvfb stopped.")
