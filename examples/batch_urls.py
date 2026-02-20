"""Batch-scrape a list of URLs from a CSV file."""

import csv
import json
import sys

from webharvest import WebHarvest

wh = WebHarvest(api_url="http://localhost:8000", api_key="wh_your_key_here")

# Read URLs from a CSV file (one URL per line, or first column)
csv_path = sys.argv[1] if len(sys.argv) > 1 else "urls.csv"

urls = []
try:
    with open(csv_path) as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip().startswith("http"):
                urls.append(row[0].strip())
except FileNotFoundError:
    print(f"File not found: {csv_path}")
    print("Usage: python batch_urls.py [urls.csv]")
    print("CSV format: one URL per line (or URL in first column)")
    sys.exit(1)

print(f"Loaded {len(urls)} URLs from {csv_path}")

# Submit batch job
batch = wh.batch_scrape(
    urls=urls,
    formats=["markdown"],
    only_main_content=True,
    poll_interval=2,
    timeout=600,
)

print(f"Batch finished: {batch.status}")
print(f"Completed: {batch.completed_count}/{batch.total_count}")

# Export results
if batch.data:
    results = []
    for page in batch.data:
        results.append({
            "url": page.url,
            "title": page.metadata.title if page.metadata else None,
            "markdown_preview": (page.markdown or "")[:200],
        })

    output_path = "batch_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} results to {output_path}")

wh.close()
