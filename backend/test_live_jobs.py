#!/usr/bin/env python3
"""Live test of the Google Jobs scraper — single-tab sequential pagination.

Usage:
    python test_live_jobs.py "software engineer" 500
    python test_live_jobs.py "penetration tester" 2000
    python test_live_jobs.py "data scientist"
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SEARXNG_URL", "")


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "software engineer"
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    print(f"{'=' * 80}")
    print(f"LIVE GOOGLE JOBS TEST (SINGLE-TAB SEQUENTIAL)")
    print(f"{'=' * 80}")
    print(f"  Query:     {query}")
    print(f"  Requested: {num} jobs")
    print()

    t0 = time.time()

    from app.services.google_jobs import google_jobs

    result = await google_jobs(
        query=query,
        num_results=num,
    )

    elapsed = time.time() - t0

    print(f"\n{'─' * 80}")
    print(f"  Success:       {result.success}")
    print(f"  Jobs returned: {len(result.jobs)}")
    print(f"  Total avail:   {result.total_results}")
    print(f"  Companies:     {result.companies}")
    print(f"  Time:          {elapsed:.1f}s")

    if not result.jobs:
        print("  No jobs found!")
        return

    # Print table
    print(f"\n{'#':>3}  {'Title':<55}  {'Company':<12}  {'Level':<10}  Location")
    print("─" * 140)

    show = min(50, len(result.jobs))
    for j in result.jobs[:show]:
        title = j.title[:53]
        if len(j.title) > 53:
            title += ".."
        company = j.company[:12]
        level = (j.experience_level or "?")[:10]
        locs = ", ".join(l.display_name for l in j.locations[:2])
        if len(j.locations) > 2:
            locs += f" +{len(j.locations) - 2}"
        print(f"{j.position:>3}  {title:<55}  {company:<12}  {level:<10}  {locs}")

    if len(result.jobs) > show:
        print(f"  ... and {len(result.jobs) - show} more jobs")

    # Stats
    all_companies = set(j.company for j in result.jobs)
    all_levels = set(j.experience_level for j in result.jobs if j.experience_level)
    all_locs = set()
    for j in result.jobs:
        for l in j.locations:
            all_locs.add(l.country or "?")

    print(f"\n--- Statistics ---")
    print(f"  Unique companies:  {all_companies}")
    print(f"  Unique levels:     {all_levels}")
    print(f"  Unique countries:  {len(all_locs)} ({', '.join(sorted(all_locs)[:10])})")

    print(f"\n{'=' * 80}")
    print(f"DONE — {len(result.jobs)} jobs for '{query}' in {elapsed:.1f}s")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(main())
