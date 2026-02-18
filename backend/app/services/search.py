import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str


class SearchEngine(ABC):
    @abstractmethod
    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        pass


class DuckDuckGoSearch(SearchEngine):
    """Search using ddgs (formerly duckduckgo-search) library."""

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        # Try the new 'ddgs' package first, fall back to old 'duckduckgo_search'
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(SearchResult(
                        url=r.get("href", r.get("url", "")),
                        title=r.get("title", ""),
                        snippet=r.get("body", r.get("description", "")),
                    ))
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            raise

        return results


class GoogleCustomSearch(SearchEngine):
    """Search using Google Custom Search JSON API (BYOK)."""

    def __init__(self, api_key: str, cx: str):
        self.api_key = api_key
        self.cx = cx

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        results = []
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "num": min(num_results, 10),
                },
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                results.append(SearchResult(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                ))

        return results


async def web_search(
    query: str,
    num_results: int = 5,
    engine: str = "duckduckgo",
    google_api_key: str | None = None,
    google_cx: str | None = None,
) -> list[SearchResult]:
    """High-level search function. Dispatches to the appropriate engine."""
    if engine == "google" and google_api_key and google_cx:
        search_engine = GoogleCustomSearch(google_api_key, google_cx)
    else:
        search_engine = DuckDuckGoSearch()

    return await search_engine.search(query, num_results)
