#!/usr/bin/env python3
"""Test the AF_initDataCallback parser against saved news_page.html.

Validates that the reverse-engineered parser in google_news.py correctly
extracts articles from the AF_initDataCallback ds:2 blob.
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.google_news import (
    _extract_af_init_data,
    _parse_af_articles,
    _safe_get,
)


def main():
    html_path = Path(__file__).parent / "news_page.html"
    if not html_path.exists():
        print("ERROR: news_page.html not found. Run test_news_scrape.py first.")
        sys.exit(1)

    print(f"Loading {html_path} ({html_path.stat().st_size:,} bytes)...")
    html = html_path.read_text(encoding="utf-8")

    # Step 1: Extract AF_initDataCallback blobs
    print("\n--- Extracting AF_initDataCallback blobs ---")
    blobs = _extract_af_init_data(html)
    if not blobs:
        print("FAIL: No AF_initDataCallback blobs found!")
        sys.exit(1)

    for b in blobs:
        data = b["data"]
        identifier = data[0] if isinstance(data, list) and data else "?"
        print(f"  {b['key']}: identifier={identifier!r}")
    print(f"  Total: {len(blobs)} blobs")

    # Step 2: Parse articles from ds:2
    print("\n--- Parsing articles from ds:2 ---")
    articles = _parse_af_articles(blobs)
    print(f"  Parsed {len(articles)} articles")

    if not articles:
        print("FAIL: No articles parsed!")
        sys.exit(1)

    # Step 3: Print sample articles
    print(f"\n--- Sample articles (first 10 of {len(articles)}) ---")
    print(f"{'#':>3}  {'Title':<60}  {'Source':<18}  {'Date':>16}  URL")
    print("-" * 160)

    for a in articles[:10]:
        title = a.title[:58]
        if len(a.title) > 58:
            title += ".."
        source = (a.source or "?")[:18]
        date = (a.date or "?")[:16]
        url = a.url[:50]
        print(f"{a.position:>3}  {title:<60}  {source:<18}  {date:>16}  {url}")

    # Step 4: Stats
    print(f"\n--- Statistics ---")
    with_url = sum(1 for a in articles if a.url and not a.url.startswith("https://news.google"))
    with_source = sum(1 for a in articles if a.source)
    with_date = sum(1 for a in articles if a.published_date)
    with_thumb = sum(1 for a in articles if a.thumbnail)

    print(f"  Total articles:     {len(articles)}")
    print(f"  With direct URLs:   {with_url}/{len(articles)}")
    print(f"  With source:        {with_source}/{len(articles)}")
    print(f"  With date:          {with_date}/{len(articles)}")
    print(f"  With thumbnail:     {with_thumb}/{len(articles)}")

    # Unique sources
    sources = {}
    for a in articles:
        s = a.source or "Unknown"
        sources[s] = sources.get(s, 0) + 1
    print(f"  Unique sources:     {len(sources)}")
    print(f"\n  Top sources:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1])[:10]:
        print(f"    {s:<25} {c:>3}")

    print(f"\nSUCCESS: Parser extracted {len(articles)} articles from AF_initDataCallback")


if __name__ == "__main__":
    main()
