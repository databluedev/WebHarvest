#!/usr/bin/env python3
"""
Crawler Initialization Timing Test
===================================
Measures the time each step of crawler.initialize() takes,
WITHOUT actually crawling. Requires Docker services running.

Usage:
  cd backend && python test_init_timing.py
"""

import asyncio
import os
import sys
import time

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def measure_imports():
    """Measure time to import heavy modules."""
    steps = {}

    t0 = time.monotonic()
    from app.config import settings  # noqa
    steps["import app.config"] = time.monotonic() - t0

    t0 = time.monotonic()
    from app.services.browser import BrowserPool, CrawlSession, browser_pool  # noqa
    steps["import browser.py"] = time.monotonic() - t0

    t0 = time.monotonic()
    from app.services.scraper import scrape_url, extract_content  # noqa
    steps["import scraper.py"] = time.monotonic() - t0

    t0 = time.monotonic()
    from app.services.crawler import WebCrawler  # noqa
    steps["import crawler.py"] = time.monotonic() - t0

    t0 = time.monotonic()
    from app.core.database import create_worker_session_factory  # noqa
    steps["import database.py"] = time.monotonic() - t0

    return steps


async def measure_browser_pool():
    """Measure browser pool initialization."""
    from app.services.browser import browser_pool

    t0 = time.monotonic()
    await browser_pool.initialize()
    t_init = time.monotonic() - t0

    return {"BrowserPool.initialize()": t_init}


async def measure_crawl_session():
    """Measure CrawlSession creation."""
    from app.services.browser import CrawlSession, browser_pool

    session = CrawlSession(browser_pool)
    t0 = time.monotonic()
    await session.start(target_url="https://www.example.com")
    t_start = time.monotonic() - t0

    t0 = time.monotonic()
    await session.stop()
    t_stop = time.monotonic() - t0

    return {
        "CrawlSession.start()": t_start,
        "CrawlSession.stop()": t_stop,
    }


async def measure_full_init():
    """Measure WebCrawler.initialize() end-to-end."""
    from app.schemas.crawl import CrawlRequest
    from app.services.crawler import WebCrawler

    request = CrawlRequest(
        url="https://www.example.com",
        max_pages=3,
        scrape_options={"formats": ["markdown"]},
    )

    crawler = WebCrawler("test-timing-job", request)
    t0 = time.monotonic()
    await crawler.initialize()
    t_init = time.monotonic() - t0

    t0 = time.monotonic()
    await crawler.cleanup()
    t_cleanup = time.monotonic() - t0

    return {
        "WebCrawler.initialize() (full)": t_init,
        "WebCrawler.cleanup()": t_cleanup,
    }


async def main():
    print("=" * 60)
    print("  CRAWLER INITIALIZATION TIMING")
    print("=" * 60)

    # 1. Module imports
    print("\n--- Module Imports ---")
    import_times = await measure_imports()
    total_import = 0
    for name, t in import_times.items():
        print(f"  {name:<30s} {t*1000:>8.1f}ms")
        total_import += t
    print(f"  {'TOTAL imports':<30s} {total_import*1000:>8.1f}ms")

    # 2. Browser pool
    print("\n--- Browser Pool ---")
    try:
        pool_times = await measure_browser_pool()
        for name, t in pool_times.items():
            print(f"  {name:<30s} {t*1000:>8.1f}ms")
    except Exception as e:
        print(f"  SKIPPED (no browser available): {e}")
        pool_times = {}

    # 3. CrawlSession
    print("\n--- CrawlSession ---")
    try:
        session_times = await measure_crawl_session()
        for name, t in session_times.items():
            print(f"  {name:<30s} {t*1000:>8.1f}ms")
    except Exception as e:
        print(f"  SKIPPED: {e}")
        session_times = {}

    # 4. Full initialize
    print("\n--- Full WebCrawler.initialize() ---")
    try:
        init_times = await measure_full_init()
        for name, t in init_times.items():
            print(f"  {name:<30s} {t*1000:>8.1f}ms")
    except Exception as e:
        print(f"  SKIPPED: {e}")
        init_times = {}

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    all_times = {**import_times, **pool_times, **session_times, **init_times}
    total = sum(all_times.values())
    print(f"  Total measured: {total:.1f}s")
    print()

    # Sorted by time (slowest first)
    sorted_times = sorted(all_times.items(), key=lambda x: -x[1])
    print("  Slowest operations:")
    for name, t in sorted_times[:5]:
        pct = (t / total * 100) if total > 0 else 0
        print(f"    {name:<35s} {t*1000:>8.1f}ms  ({pct:>4.1f}%)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
