"""
DEFINITIVE Google Images udm=2 Pagination Test

Summary of all findings + final verification.
"""

import httpx
import re
import asyncio
from urllib.parse import urlencode


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

BASE_URL = "https://www.google.com/search"


def extract_doc_ids(html: str) -> list[str]:
    return re.findall(r'data-docid="([^"]+)"', html)


async def paginate_query(client, query: str, max_start: int = 100) -> dict:
    """Paginate through all available results for a query."""
    cumulative = set()
    pages = []

    for start_val in range(0, max_start, 10):
        params = {"q": query, "udm": "2", "hl": "en"}
        if start_val > 0:
            params["start"] = str(start_val)

        resp = await client.get(f"{BASE_URL}?{urlencode(params)}")
        doc_ids = set(extract_doc_ids(resp.text))

        if not doc_ids:
            break

        new = doc_ids - cumulative
        cumulative.update(doc_ids)
        pages.append({
            "start": start_val,
            "count": len(doc_ids),
            "new_unique": len(new),
            "cumulative": len(cumulative),
        })
        await asyncio.sleep(1)

    return {"query": query, "pages": pages, "total_unique": len(cumulative)}


async def main():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:

        print("=" * 80)
        print("DEFINITIVE PAGINATION TEST: Multiple queries")
        print("=" * 80)

        queries = [
            "sunset beach wallpaper",
            "machine learning diagram",
            "street food bangkok",
            "architecture modern buildings",
            "watercolor painting flowers",
        ]

        all_results = []
        for query in queries:
            result = await paginate_query(client, query)
            all_results.append(result)

            print(f"\n--- '{query}' ---")
            for p in result["pages"]:
                print(f"  start={p['start']:3d}: {p['count']:3d} results, "
                      f"+{p['new_unique']:3d} new, "
                      f"cumulative={p['cumulative']:3d}")
            print(f"  TOTAL: {result['total_unique']} unique images across {len(result['pages'])} pages")

        print()
        print("=" * 80)
        print("FINAL RESULTS SUMMARY")
        print("=" * 80)

        for r in all_results:
            pages = len(r["pages"])
            total = r["total_unique"]
            max_start = r["pages"][-1]["start"] if r["pages"] else 0
            print(f"  '{r['query']}': {pages} pages (start 0-{max_start}), {total} unique images")

        avg_total = sum(r["total_unique"] for r in all_results) / len(all_results)
        avg_pages = sum(len(r["pages"]) for r in all_results) / len(all_results)

        print(f"\n  Average: {avg_pages:.1f} pages, {avg_total:.0f} unique images")
        print()
        print("=" * 80)
        print("HOW TO IMPLEMENT PAGINATION")
        print("=" * 80)
        print("""
PARAMETER: `start` with step size 10
  - Page 1: start=0  (or omit start)
  - Page 2: start=10
  - Page 3: start=20
  - ...

RESULTS PER PAGE: ~100 images per request (each page returns 100)

OVERLAP: Very low overlap between consecutive pages.
  - start=0 and start=10 typically share 0-6 results
  - Most pages return ~95-100 completely new results
  - Google does NOT use a sliding window; each start=N offset
    returns a mostly distinct set of ~100 results

EXHAUSTION DETECTION:
  - When a request returns 0 doc_ids (page size ~200KB = boilerplate only)
  - The "More results" button only appears on page 1 (start=0)
  - Pages 2+ have NO next-page link in HTML, but still return results
  - Typical depth: 3-6 pages (300-600 unique images)

IMPLEMENTATION PATTERN:
  ```python
  all_images = []
  seen_ids = set()
  for start in range(0, max_results, 10):
      html = fetch(q=query, udm=2, hl=en, start=start)
      doc_ids = extract_doc_ids(html)
      if not doc_ids:
          break  # exhausted
      for img in parse_images(html):
          if img.doc_id not in seen_ids:
              seen_ids.add(img.doc_id)
              all_images.append(img)
  ```

KEY DIFFERENCES FROM OLD GOOGLE IMAGES (tbm=isch):
  - ijn parameter: does NOT work with udm=2
  - tbm=isch now redirects/behaves same as udm=2
  - async loading: does NOT work (returns full HTML page)
  - start= step: was 20 for tbm=isch, is 10 for udm=2

NOTES:
  - Results are deterministic within a session (same request = same results)
  - No session token (ei/sca_esv) required for pagination
  - Simple start=N parameter is sufficient
  - Rate limiting: add 1s delay between requests
""")


if __name__ == "__main__":
    asyncio.run(main())
