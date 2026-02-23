import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import quote_plus

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


class PlaywrightGoogleSearch(SearchEngine):
    """Search Google with a real Playwright browser — most reliable results.

    Uses the existing BrowserPool (stealth + fingerprinting) to navigate to
    Google, render the SERP, and extract organic results from the DOM.
    Falls through gracefully if the browser pool is unavailable.
    """

    async def search(self, query: str, num_results: int) -> list[SearchResult]:
        from app.services.browser import browser_pool

        await browser_pool.initialize()

        results: list[SearchResult] = []
        search_url = (
            f"https://www.google.com/search?q={quote_plus(query)}"
            f"&num={min(num_results + 5, 20)}&hl=en"
        )

        async with browser_pool.get_page(stealth=True) as page:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

            # Wait for organic results container
            try:
                await page.wait_for_selector("#search, #rso", timeout=5000)
            except Exception:
                pass  # Results may be in a different container

            # Extract organic search results from the rendered DOM
            raw = await page.evaluate(
                """() => {
                const results = [];
                const seen = new Set();

                // Google wraps each organic result in a div.g containing an h3
                const containers = document.querySelectorAll(
                    '#rso .g, #search .g, [data-sokoban-container] .g'
                );

                for (const g of containers) {
                    const h3 = g.querySelector('h3');
                    if (!h3) continue;

                    const link = h3.closest('a');
                    if (!link || !link.href) continue;

                    let url = link.href;

                    // Resolve Google redirect URLs (/url?q=...)
                    try {
                        const u = new URL(url);
                        if (u.hostname.includes('google') && u.searchParams.has('q')) {
                            url = u.searchParams.get('q');
                        }
                    } catch {}

                    if (!url || !url.startsWith('http')) continue;
                    if (url.includes('google.com/search')) continue;
                    if (url.includes('accounts.google.com')) continue;
                    if (seen.has(url)) continue;
                    seen.add(url);

                    const title = (h3.textContent || '').trim();
                    if (!title) continue;

                    // Extract snippet from the result container
                    let snippet = '';

                    // Try known snippet selectors first
                    const snippetEl = g.querySelector(
                        '[data-sncf="1"], .VwiC3b, [style*="-webkit-line-clamp"], span.st'
                    );
                    if (snippetEl) {
                        snippet = (snippetEl.textContent || '').trim();
                    }

                    // Fallback: find the longest text block that isn't the title
                    if (!snippet) {
                        for (const el of g.querySelectorAll('div, span')) {
                            if (el.querySelector('h3') || el.querySelector('cite')) continue;
                            const t = (el.textContent || '').trim();
                            if (t.length > 40 && t.length < 500
                                && t.length > snippet.length && t !== title) {
                                snippet = t;
                            }
                        }
                    }

                    results.push({ url, title, snippet });
                }

                return results;
            }"""
            )

            for item in raw[:num_results]:
                results.append(
                    SearchResult(
                        url=item["url"],
                        title=item["title"],
                        snippet=item.get("snippet", ""),
                    )
                )

        if not results:
            logger.warning("Playwright Google search returned 0 organic results")

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

    Chains (Playwright Google is the most reliable — real browser + stealth):
      google:     Playwright Google → Google API (if keys) → DDGS google → DuckDuckGo → Brave
      duckduckgo: DuckDuckGo → Playwright Google → DDGS google → Brave
      brave:      Brave → DuckDuckGo → Playwright Google → DDGS google
    """
    engines: list[tuple[str, SearchEngine]] = []

    # ── Primary engine ──────────────────────────────────────────────
    if engine == "google":
        engines.append(("google_playwright", PlaywrightGoogleSearch()))
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

    if "google_playwright" not in seen:
        fallbacks.append(("google_playwright", PlaywrightGoogleSearch()))

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
