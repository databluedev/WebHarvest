import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import settings

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
                    results.append(
                        SearchResult(
                            url=r.get("href", r.get("url", "")),
                            title=r.get("title", ""),
                            snippet=r.get("body", r.get("description", "")),
                        )
                    )
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            raise

        return results


class GoogleScrapedSearch(SearchEngine):
    """Search Google via DDGS google backend — no API key needed."""

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(
                    query, max_results=num_results, backend="google"
                ):
                    results.append(
                        SearchResult(
                            url=r.get("href", r.get("url", "")),
                            title=r.get("title", ""),
                            snippet=r.get("body", r.get("description", "")),
                        )
                    )
        except Exception as e:
            logger.error(f"Google scraped search failed: {e}")
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
                results.append(
                    SearchResult(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                    )
                )

        return results


class BraveSearch(SearchEngine):
    """Search using Brave Search API (free tier: 2000 queries/month)."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        results = []
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": query,
                    "count": min(num_results, 20),
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("web", {}).get("results", []):
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("description", ""),
                    )
                )

        return results


class SearXNGSearch(SearchEngine):
    """Search via self-hosted SearXNG — aggregates Google, Bing, Brave, DDG."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json", "pageno": 1},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", [])[:num_results]:
            results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                )
            )
        return results


async def web_search(
    query: str,
    num_results: int = 5,
    engine: str = "duckduckgo",
    google_api_key: str | None = None,
    google_cx: str | None = None,
    brave_api_key: str | None = None,
) -> list[SearchResult]:
    """High-level search function with automatic fallback chain.

    Chains (SearXNG aggregates Google + Bing + Brave + DDG):
      google:     SearXNG → Google API (if keys) → DDGS google → DuckDuckGo → Brave
      duckduckgo: DuckDuckGo → SearXNG → DDGS google → Brave
      brave:      Brave → DuckDuckGo → SearXNG → DDGS google
    """
    engines: list[tuple[str, SearchEngine]] = []

    searxng_url = settings.SEARXNG_URL

    # ── Primary engine ──────────────────────────────────────────────
    if engine == "google":
        if searxng_url:
            engines.append(("searxng", SearXNGSearch(searxng_url)))
        if google_api_key and google_cx:
            engines.append(("google_api", GoogleCustomSearch(google_api_key, google_cx)))
        engines.append(("google_scraped", GoogleScrapedSearch()))
    elif engine == "brave":
        brave_key = brave_api_key or settings.BRAVE_SEARCH_API_KEY
        if brave_key:
            engines.append(("brave", BraveSearch(brave_key)))
    else:
        engines.append(("duckduckgo", DuckDuckGoSearch()))

    # ── Fallback engines (deduplicated) ─────────────────────────────
    seen = {name for name, _ in engines}

    fallbacks: list[tuple[str, SearchEngine]] = []

    if "duckduckgo" not in seen:
        fallbacks.append(("duckduckgo", DuckDuckGoSearch()))

    if "searxng" not in seen and searxng_url:
        fallbacks.append(("searxng", SearXNGSearch(searxng_url)))

    if "google_scraped" not in seen:
        fallbacks.append(("google_scraped", GoogleScrapedSearch()))

    brave_key = brave_api_key or settings.BRAVE_SEARCH_API_KEY
    if "brave" not in seen and brave_key:
        fallbacks.append(("brave", BraveSearch(brave_key)))

    if "google_api" not in seen and google_api_key and google_cx:
        fallbacks.append(("google_api", GoogleCustomSearch(google_api_key, google_cx)))

    engines.extend(fallbacks)

    # ── Try each engine in order ────────────────────────────────────
    last_error = None
    for engine_name, search_engine in engines:
        try:
            results = await search_engine.search(query, num_results)
            if results:
                logger.info(
                    f"Search succeeded with {engine_name}: {len(results)} results"
                )
                return results
            logger.warning(f"{engine_name} returned no results, trying fallback")
        except Exception as e:
            logger.warning(f"{engine_name} search failed: {e}, trying fallback")
            last_error = e

    # All engines failed
    if last_error:
        raise last_error
    return []
