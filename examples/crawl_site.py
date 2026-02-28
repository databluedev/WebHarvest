"""Crawl a website and export results to JSON."""

import json

from webharvest import DataBlue

wh = DataBlue(api_url="http://localhost:8000", api_key="wh_your_key_here")

# Start crawl and wait for completion (blocking)
print("Starting crawl...")
status = wh.crawl(
    "https://example.com",
    max_pages=20,
    max_depth=2,
    concurrency=3,
    poll_interval=3,
    timeout=300,
)

print(f"Crawl finished: {status.status}")
print(f"Pages crawled: {status.completed_pages}/{status.total_pages}")

# Export results
if status.data:
    results = []
    for page in status.data:
        results.append({
            "url": page.url,
            "title": page.metadata.title if page.metadata else None,
            "word_count": page.metadata.word_count if page.metadata else 0,
            "markdown_length": len(page.markdown or ""),
        })

    with open("crawl_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} pages to crawl_results.json")

wh.close()
