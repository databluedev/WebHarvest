#!/usr/bin/env python3
"""Live test of the Google News scraper — end-to-end with nodriver.

Runs the full google_news() pipeline: nodriver → RSS → SearXNG
and prints the results.

Usage:
    python test_live_news.py "artificial intelligence" 200
    python test_live_news.py "bitcoin"
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Minimal env setup
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SEARXNG_URL", "")


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "artificial intelligence"
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    print(f"{'=' * 70}")
    print(f"LIVE GOOGLE NEWS TEST")
    print(f"{'=' * 70}")
    print(f"  Query:    {query}")
    print(f"  Requested: {num} articles")
    print()

    # --- Step 1: Test nodriver directly ---
    print("─── Strategy 1: nodriver (news.google.com) ───")
    t0 = time.time()

    from app.services.google_news import (
        _build_news_google_url,
        _extract_af_init_data,
        _fetch_news_google_html,
        _parse_af_articles,
    )

    url = _build_news_google_url(query, lang="en", country="US")
    print(f"  URL: {url}")

    html = await _fetch_news_google_html(url)
    t_fetch = time.time() - t0

    if not html:
        print(f"  FAILED: No HTML returned ({t_fetch:.1f}s)")
    else:
        print(f"  HTML: {len(html):,} bytes ({t_fetch:.1f}s)")

        blobs = _extract_af_init_data(html)
        if blobs:
            print(f"  AF_initDataCallback blobs: {[b['key'] for b in blobs]}")
            articles = _parse_af_articles(blobs)
            print(f"  Articles parsed: {len(articles)}")

            if articles:
                with_url = sum(1 for a in articles if a.url and "news.google" not in a.url)
                with_src = sum(1 for a in articles if a.source)
                with_date = sum(1 for a in articles if a.published_date)
                with_thumb = sum(1 for a in articles if a.thumbnail)
                print(f"  Direct URLs: {with_url}/{len(articles)}")
                print(f"  With source: {with_src}/{len(articles)}")
                print(f"  With date:   {with_date}/{len(articles)}")
                print(f"  With thumb:  {with_thumb}/{len(articles)}")
        else:
            print("  FAILED: No AF_initDataCallback found")
            # Save HTML for debugging
            debug_path = Path(__file__).parent / "debug_news.html"
            debug_path.write_text(html[:50000], encoding="utf-8")
            print(f"  Saved first 50KB to {debug_path}")

    # --- Step 2: Test RSS ---
    print()
    print("─── Strategy 2: RSS (news.google.com/rss) ───")
    t1 = time.time()

    from app.services.google_news import _search_via_rss

    rss_articles = await _search_via_rss(query, num, "en", "US")
    t_rss = time.time() - t1

    if rss_articles:
        print(f"  Articles: {len(rss_articles)} ({t_rss:.1f}s)")
    else:
        print(f"  FAILED or 0 articles ({t_rss:.1f}s)")

    # --- Step 3: Print combined results ---
    print()
    print("─── Combined Results ───")

    all_articles = []
    seen = set()

    # Add nodriver articles first (best quality)
    if html and blobs:
        nd_articles = _parse_af_articles(blobs)
        for a in nd_articles:
            norm = a.url.rstrip("/")
            if norm not in seen:
                seen.add(norm)
                all_articles.append(a)

    # Add RSS articles
    if rss_articles:
        for a in rss_articles:
            norm = a.url.rstrip("/")
            if norm not in seen:
                seen.add(norm)
                all_articles.append(a)

    # Re-number
    for i, a in enumerate(all_articles):
        a.position = i + 1

    total = len(all_articles)
    print(f"  Total unique articles: {total}")

    if not all_articles:
        print("  No articles found!")
        return

    # Print table
    print()
    print(f"{'#':>3}  {'Title':<65}  {'Source':<20}  {'Date':>16}  URL")
    print("─" * 170)

    for a in all_articles[:30]:
        title = a.title[:63]
        if len(a.title) > 63:
            title += ".."
        source = (a.source or "?")[:20]
        date = (a.date or a.published_date or "?")[:16]
        url_short = a.url[:55]
        print(f"{a.position:>3}  {title:<65}  {source:<20}  {date:>16}  {url_short}")

    if total > 30:
        print(f"  ... and {total - 30} more articles")

    # Source distribution
    sources = {}
    for a in all_articles:
        s = a.source or "Unknown"
        sources[s] = sources.get(s, 0) + 1

    print(f"\n  Unique sources: {len(sources)}")
    print(f"  Top 10:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1])[:10]:
        print(f"    {s:<28} {c:>3}")

    # Timing
    print(f"\n  nodriver fetch: {t_fetch:.1f}s")
    print(f"  RSS fetch:      {t_rss:.1f}s")
    print(f"  Total:          {t_fetch + t_rss:.1f}s")

    print(f"\n{'=' * 70}")
    print(f"DONE — {total} unique articles for '{query}'")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
