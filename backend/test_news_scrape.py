#!/usr/bin/env python3
"""Standalone Google News scraper using nodriver.

Fetches the Google News search page for a query, waits for articles to load,
saves the full rendered HTML, and extracts any embedded JS data blobs
(AF_initDataCallback, AF_dataServiceRequests, etc.).

Usage:
    python test_news_scrape.py
"""

import asyncio
import json
import logging
import re
import shutil
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────
URL = "https://news.google.com/search?q=el%20mencho&hl=en-IN&gl=IN&ceid=IN:en"
OUTPUT_DIR = Path(__file__).parent
HTML_FILE = OUTPUT_DIR / "news_page.html"
JSON_FILE = OUTPUT_DIR / "news_data.json"


def find_chrome() -> str | None:
    """Locate a Chrome/Chromium binary."""
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            return p
    return None


def extract_data_blobs(html: str) -> dict:
    """Extract embedded JavaScript data from the HTML.

    Google News embeds structured data in several patterns:
    - AF_initDataCallback({key: '...', data: [...]})
    - AF_dataServiceRequests
    - <script type="application/ld+json">
    - window.__data or similar global JS objects
    """
    results = {
        "af_init_data_callbacks": [],
        "ld_json": [],
        "inline_script_data": [],
        "rso_data": [],
    }

    # 1) AF_initDataCallback calls
    # Pattern: AF_initDataCallback({key: 'ds:N', ...hash..., data: [...]});
    af_pattern = re.compile(
        r"AF_initDataCallback\s*\(\s*(\{.*?\})\s*\)\s*;",
        re.DOTALL,
    )
    for match in af_pattern.finditer(html):
        raw = match.group(1)
        # Extract the key
        key_match = re.search(r"key:\s*'([^']+)'", raw)
        key = key_match.group(1) if key_match else "unknown"

        # Try to extract the data array
        data_match = re.search(r"data:\s*(\[.*)", raw, re.DOTALL)
        if data_match:
            data_str = data_match.group(1)
            # Find balanced brackets
            depth = 0
            end = 0
            for i, ch in enumerate(data_str):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            data_str = data_str[:end]
            try:
                parsed = json.loads(data_str)
                results["af_init_data_callbacks"].append({
                    "key": key,
                    "data": parsed,
                    "data_length": len(data_str),
                })
            except json.JSONDecodeError:
                results["af_init_data_callbacks"].append({
                    "key": key,
                    "data_raw_preview": data_str[:500],
                    "data_length": len(data_str),
                    "parse_error": True,
                })

    # 2) JSON-LD structured data
    ld_pattern = re.compile(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in ld_pattern.finditer(html):
        try:
            parsed = json.loads(match.group(1))
            results["ld_json"].append(parsed)
        except json.JSONDecodeError:
            results["ld_json"].append({"raw_preview": match.group(1)[:500], "parse_error": True})

    # 3) Look for c-wiz data attributes and other Google-specific data
    cwiz_pattern = re.compile(r'data-p=["\'](%7B.*?)["\']', re.DOTALL)
    for match in cwiz_pattern.finditer(html):
        from urllib.parse import unquote
        try:
            decoded = unquote(match.group(1))
            parsed = json.loads(decoded)
            results["inline_script_data"].append(parsed)
        except Exception:
            pass

    # 4) Extract RSO/article data from script tags
    # Google sometimes embeds article data in script tags as JS arrays
    script_pattern = re.compile(
        r"<script\s+nonce=[^>]*>(.*?)</script>",
        re.DOTALL,
    )
    for match in script_pattern.finditer(html):
        content = match.group(1).strip()
        if len(content) > 200 and ("article" in content.lower() or "news" in content.lower()):
            results["rso_data"].append({
                "preview": content[:1000],
                "length": len(content),
            })

    # 5) Look for window.__data or similar global data assignments
    global_data_pattern = re.compile(
        r"(?:window\.__data|window\._sharedData|window\.INITIAL_DATA)\s*=\s*(\{.*?\})\s*;",
        re.DOTALL,
    )
    for match in global_data_pattern.finditer(html):
        try:
            parsed = json.loads(match.group(1))
            results["inline_script_data"].append({"type": "global_data", "data": parsed})
        except json.JSONDecodeError:
            results["inline_script_data"].append({
                "type": "global_data",
                "raw_preview": match.group(1)[:500],
                "parse_error": True,
            })

    return results


async def main():
    import nodriver as uc
    from pyvirtualdisplay import Display

    chrome_path = find_chrome()
    if not chrome_path:
        logger.error("No Chrome/Chromium binary found. Install chromium first.")
        return

    logger.info("Using Chrome at: %s", chrome_path)
    logger.info("Target URL: %s", URL)

    # Start virtual display (Xvfb) so headed Chrome works without a monitor
    display = Display(visible=False, size=(1920, 1080))
    display.start()
    logger.info("Xvfb started on display :%s", display.display)

    browser = None
    try:
        # Launch browser
        t0 = time.time()
        browser = await uc.start(
            headless=False,
            browser_executable_path=chrome_path,
            sandbox=False,
            lang="en-US",
            browser_args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,1080",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("Browser started in %.1fs", time.time() - t0)

        # Navigate to Google News
        t1 = time.time()
        tab = await browser.get(URL)
        logger.info("Navigation started in %.1fs", time.time() - t1)

        # Wait for article content to appear
        # Google News uses <article> elements and c-wiz components
        selectors_to_try = [
            "article",
            "c-wiz article",
            "div[class*='IBr9hb']",    # news card container
            "a[class*='JtKRv']",        # article link
            "div[class*='xrnccd']",     # article card
            "main",
        ]
        found_selector = None
        for sel in selectors_to_try:
            try:
                await tab.select(sel, timeout=8)
                found_selector = sel
                logger.info("Found content with selector: %s", sel)
                break
            except Exception:
                continue

        if not found_selector:
            logger.warning("No article selectors matched -- page may still have content")

        # Let JS settle and lazy content load
        logger.info("Waiting 5s for JS to settle and lazy content to load...")
        await tab.sleep(5)

        # Scroll down to trigger lazy loading
        logger.info("Scrolling to trigger lazy loading...")
        for i in range(3):
            await tab.evaluate("window.scrollBy(0, window.innerHeight)")
            await tab.sleep(1.5)
        # Scroll back to top
        await tab.evaluate("window.scrollTo(0, 0)")
        await tab.sleep(1)

        # Get full rendered HTML
        html = await tab.get_content()
        if not html:
            html = await tab.evaluate("document.documentElement.outerHTML")

        if not html:
            logger.error("Failed to get page HTML")
            return

        # Save HTML
        HTML_FILE.write_text(html, encoding="utf-8")
        logger.info("Saved HTML to %s (%d bytes)", HTML_FILE, len(html))

        # Extract and save data blobs
        data_blobs = extract_data_blobs(html)

        # Add page metadata
        page_title = await tab.evaluate("document.title") or ""
        page_url = await tab.evaluate("window.location.href") or ""
        article_count = await tab.evaluate("document.querySelectorAll('article').length") or 0
        link_count = await tab.evaluate("document.querySelectorAll('a').length") or 0

        # Try to get article headlines
        headlines_js = """
        (() => {
            const articles = document.querySelectorAll('article');
            const headlines = [];
            articles.forEach((a, i) => {
                const link = a.querySelector('a[href]');
                const heading = a.querySelector('h3, h4, [class*="title"], [class*="headline"]');
                const source = a.querySelector('div[class*="source"], span[class*="source"], [data-n-tid]');
                const timeEl = a.querySelector('time, [datetime]');
                headlines.push({
                    index: i,
                    text: (heading || link || a).innerText.trim().substring(0, 200),
                    href: link ? link.href : null,
                    source: source ? source.innerText.trim() : null,
                    time: timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText.trim()) : null,
                });
            });
            return JSON.stringify(headlines);
        })()
        """
        headlines_raw = await tab.evaluate(headlines_js)
        try:
            headlines = json.loads(headlines_raw) if headlines_raw else []
        except (json.JSONDecodeError, TypeError):
            headlines = []

        output = {
            "metadata": {
                "url": page_url,
                "title": page_title,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "html_size_bytes": len(html),
                "article_elements": article_count,
                "link_elements": link_count,
                "headlines_found": len(headlines),
            },
            "headlines": headlines,
            "data_blobs": data_blobs,
        }

        JSON_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        logger.info("Saved data to %s", JSON_FILE)

        # Print stats
        print("\n" + "=" * 70)
        print("GOOGLE NEWS SCRAPE RESULTS")
        print("=" * 70)
        print(f"  URL:              {page_url}")
        print(f"  Title:            {page_title}")
        print(f"  HTML size:        {len(html):,} bytes")
        print(f"  <article> count:  {article_count}")
        print(f"  <a> links:        {link_count}")
        print(f"  Headlines found:  {len(headlines)}")
        print(f"  AF_initData keys: {len(data_blobs['af_init_data_callbacks'])}")
        print(f"  JSON-LD blocks:   {len(data_blobs['ld_json'])}")
        print(f"  Inline data:      {len(data_blobs['inline_script_data'])}")
        print(f"  Script data:      {len(data_blobs['rso_data'])}")
        print()

        if headlines:
            print("HEADLINES:")
            print("-" * 70)
            for h in headlines[:15]:
                source = f" [{h['source']}]" if h.get("source") else ""
                time_str = f" ({h['time']})" if h.get("time") else ""
                print(f"  {h['index']+1:2d}. {h['text'][:100]}{source}{time_str}")
            if len(headlines) > 15:
                print(f"  ... and {len(headlines) - 15} more")
            print()

        print(f"HTML saved to:  {HTML_FILE}")
        print(f"Data saved to:  {JSON_FILE}")
        print("=" * 70)

    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass
        try:
            display.stop()
        except Exception:
            pass
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
