#!/usr/bin/env python3
"""
Crawl Worker Timing Test
========================
Measures the time from POST /v1/crawl to each state transition:
  - pending → running  (task pickup + init)
  - running → first page saved
  - running → completed (all pages)

Usage:
  # Against local dev:
  python test_crawl_timing.py

  # Against production:
  python test_crawl_timing.py --api-url https://your-api.com --email user@example.com --password pass

  # Custom URL and pages:
  python test_crawl_timing.py --url https://example.com --max-pages 3
"""

import argparse
import json
import sys
import time

import httpx

# Defaults
DEFAULT_API = "http://localhost:8000"
DEFAULT_EMAIL = "rajaa0049@gmail.com"
DEFAULT_PASSWORD = "password"
DEFAULT_URL = "https://www.amazon.in/"
DEFAULT_MAX_PAGES = 3
POLL_INTERVAL = 0.5  # seconds between polls


def login(client: httpx.Client, api: str, email: str, password: str) -> str:
    """Get JWT token."""
    print(f"[auth] Logging in as {email}...")
    r = client.post(f"{api}/v1/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        print(f"[auth] FAILED: {r.status_code} {r.text}")
        sys.exit(1)
    token = r.json()["access_token"]
    print(f"[auth] Got token: {token[:20]}...")
    return token


def start_crawl(client: httpx.Client, api: str, token: str, url: str, max_pages: int) -> str:
    """POST /v1/crawl — returns job_id."""
    payload = {
        "url": url,
        "max_pages": max_pages,
        "scrape_options": {
            "formats": ["markdown"],
        },
    }
    print(f"\n[crawl] Starting crawl: {url} (max_pages={max_pages})")
    t0 = time.monotonic()
    r = client.post(
        f"{api}/v1/crawl",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    elapsed = (time.monotonic() - t0) * 1000
    if r.status_code != 200:
        print(f"[crawl] FAILED: {r.status_code} {r.text}")
        sys.exit(1)
    data = r.json()
    job_id = data["job_id"]
    print(f"[crawl] Job created: {job_id} ({elapsed:.0f}ms)")
    return job_id


def poll_crawl(client: httpx.Client, api: str, token: str, job_id: str):
    """Poll GET /v1/crawl/{job_id} and measure state transitions."""

    t_start = time.monotonic()
    t_running = None
    t_first_page = None
    t_completed = None
    last_status = None
    last_pages = 0
    poll_count = 0

    print(f"\n{'─' * 70}")
    print(f"{'Time':>8s}  {'Status':<12s}  {'Pages':<10s}  Event")
    print(f"{'─' * 70}")

    while True:
        r = client.get(
            f"{api}/v1/crawl/{job_id}?page=1&per_page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            print(f"[poll] Error: {r.status_code}")
            break

        data = r.json()
        status = data["status"]
        completed = data.get("completed_pages", 0)
        total = data.get("total_pages", 0)
        elapsed = time.monotonic() - t_start
        poll_count += 1

        # Detect transitions
        if status != last_status:
            event = f"→ {status}"

            if status == "running" and t_running is None:
                t_running = elapsed
                event += f"  (pickup: {elapsed:.1f}s)"

            if status in ("completed", "failed", "cancelled"):
                t_completed = elapsed
                event += f"  (total: {elapsed:.1f}s)"

            print(f"{elapsed:7.1f}s  {status:<12s}  {completed}/{total:<7}  {event}")
            last_status = status

        if completed > last_pages:
            if t_first_page is None and completed >= 1:
                t_first_page = elapsed
                print(f"{elapsed:7.1f}s  {status:<12s}  {completed}/{total:<7}  ★ First page saved ({elapsed:.1f}s)")
            elif completed > last_pages:
                print(f"{elapsed:7.1f}s  {status:<12s}  {completed}/{total:<7}  Page {completed} saved")
            last_pages = completed

        if status in ("completed", "failed", "cancelled"):
            break

        time.sleep(POLL_INTERVAL)

    # Summary
    print(f"\n{'═' * 70}")
    print(f"  TIMING SUMMARY — {job_id}")
    print(f"{'═' * 70}")
    print(f"  POST → running:     {t_running:.1f}s" if t_running else "  POST → running:     N/A")
    print(f"  POST → first page:  {t_first_page:.1f}s" if t_first_page else "  POST → first page:  N/A")
    print(f"  POST → completed:   {t_completed:.1f}s" if t_completed else "  POST → completed:   N/A")
    if t_running and t_first_page:
        print(f"  running → 1st page: {t_first_page - t_running:.1f}s")
    if t_first_page and t_completed and last_pages > 1:
        print(f"  Avg per page:       {(t_completed - t_first_page) / (last_pages - 1):.1f}s (pages 2-{last_pages})")
    print(f"  Total pages:        {last_pages}")
    print(f"  Final status:       {last_status}")
    print(f"  Poll requests:      {poll_count}")
    print(f"{'═' * 70}")

    return {
        "job_id": job_id,
        "t_running": t_running,
        "t_first_page": t_first_page,
        "t_completed": t_completed,
        "pages": last_pages,
        "status": last_status,
    }


def main():
    parser = argparse.ArgumentParser(description="Crawl Worker Timing Test")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Login email")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Login password")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL to crawl (default: {DEFAULT_URL})")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help=f"Max pages (default: {DEFAULT_MAX_PAGES})")
    parser.add_argument("--runs", type=int, default=1, help="Number of consecutive runs (tests warm pool)")
    args = parser.parse_args()

    client = httpx.Client(timeout=30.0)

    # Auth
    token = login(client, args.api_url, args.email, args.password)

    # Run crawl(s)
    results = []
    for i in range(args.runs):
        if args.runs > 1:
            print(f"\n{'▓' * 70}")
            print(f"  RUN {i + 1}/{args.runs}")
            print(f"{'▓' * 70}")

        job_id = start_crawl(client, args.api_url, token, args.url, args.max_pages)
        result = poll_crawl(client, args.api_url, token, job_id)
        results.append(result)

        if i < args.runs - 1:
            print(f"\n  Waiting 5s before next run (let worker settle)...")
            time.sleep(5)

    # Multi-run summary
    if len(results) > 1:
        print(f"\n{'█' * 70}")
        print(f"  MULTI-RUN COMPARISON")
        print(f"{'█' * 70}")
        print(f"  {'Run':<5s}  {'Pickup':>8s}  {'1st Page':>10s}  {'Total':>8s}  {'Pages':>6s}  Status")
        print(f"  {'─' * 60}")
        for i, r in enumerate(results):
            pickup = f"{r['t_running']:.1f}s" if r['t_running'] else "N/A"
            first = f"{r['t_first_page']:.1f}s" if r['t_first_page'] else "N/A"
            total = f"{r['t_completed']:.1f}s" if r['t_completed'] else "N/A"
            print(f"  {i+1:<5d}  {pickup:>8s}  {first:>10s}  {total:>8s}  {r['pages']:>6d}  {r['status']}")

        # Averages
        pickups = [r['t_running'] for r in results if r['t_running']]
        firsts = [r['t_first_page'] for r in results if r['t_first_page']]
        totals = [r['t_completed'] for r in results if r['t_completed']]
        print(f"  {'─' * 60}")
        if pickups:
            print(f"  {'Avg':<5s}  {sum(pickups)/len(pickups):>7.1f}s  {sum(firsts)/len(firsts):>9.1f}s  {sum(totals)/len(totals):>7.1f}s")
        print(f"{'█' * 70}")


if __name__ == "__main__":
    main()
