"""Basic scrape example — extract markdown content from a single URL."""

from webharvest import WebHarvest

# Connect with API key (generate one at /api-keys in the dashboard)
wh = WebHarvest(api_url="http://localhost:8000", api_key="wh_your_key_here")

# Or connect with email/password:
# wh = WebHarvest(api_url="http://localhost:8000")
# wh.login("user@example.com", "password")

# Scrape a page — returns markdown, HTML, links, and metadata
result = wh.scrape(
    "https://example.com",
    formats=["markdown", "links", "structured_data"],
    only_main_content=True,
)

if result.success:
    print("=== Markdown ===")
    print(result.data.markdown[:500])
    print()
    print(f"=== Links ({len(result.data.links or [])} found) ===")
    for link in (result.data.links or [])[:10]:
        print(f"  {link}")
else:
    print(f"Scrape failed: {result.error}")

wh.close()
