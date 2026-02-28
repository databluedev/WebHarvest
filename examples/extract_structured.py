"""LLM extraction with structured output — extract data from a page using AI."""

from webharvest import DataBlue

wh = DataBlue(api_url="http://localhost:8000", api_key="wh_your_key_here")

# First, make sure you've added an LLM key in Settings (e.g., OpenAI key)
# via the dashboard at /settings or via the API:
#
#   curl -X PUT http://localhost:8000/v1/settings/llm-keys \
#     -H "Authorization: Bearer YOUR_TOKEN" \
#     -d '{"provider": "openai", "api_key": "sk-...", "is_default": true}'

# Scrape + extract in one call
result = wh.scrape(
    "https://news.ycombinator.com",
    formats=["markdown"],
    extract={
        "prompt": "Extract the top 5 stories. For each story, return the title, URL, points, and number of comments.",
        "schema_": {
            "type": "object",
            "properties": {
                "stories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "points": {"type": "integer"},
                            "comments": {"type": "integer"},
                        },
                    },
                }
            },
        },
    },
)

if result.success and result.data.extract:
    print("=== Extracted Stories ===")
    stories = result.data.extract.get("stories", [])
    for i, story in enumerate(stories, 1):
        print(f"{i}. {story.get('title', 'N/A')}")
        print(f"   URL: {story.get('url', 'N/A')}")
        print(f"   Points: {story.get('points', 'N/A')} | Comments: {story.get('comments', 'N/A')}")
        print()
else:
    print(f"Failed: {result.error}")

wh.close()
