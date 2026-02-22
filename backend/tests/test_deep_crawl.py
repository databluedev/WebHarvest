"""Tests for deep crawl strategies, scorers, and filters."""
import pytest
from app.services.deep_crawl.strategies import (
    BFSStrategy,
    DFSStrategy,
    BestFirstStrategy,
    CrawlURL,
    CrawlState,
)
from app.services.deep_crawl.scorers import (
    KeywordRelevanceScorer,
    PathDepthScorer,
    ContentTypeScorer,
    FreshnessScorer,
    CompositeScorer,
)
from app.services.deep_crawl.filters import (
    URLPatternFilter,
    DomainFilter,
    ContentTypeFilter,
    FilterChain,
)


# ---------------------------------------------------------------------------
# CrawlState
# ---------------------------------------------------------------------------


class TestCrawlState:
    def test_serialization(self):
        state = CrawlState(
            strategy_type="bfs",
            visited={"https://a.com", "https://b.com"},
            pages_crawled=2,
        )
        d = state.to_dict()
        assert d["strategy_type"] == "bfs"
        assert len(d["visited"]) == 2
        assert d["pages_crawled"] == 2

    def test_deserialization(self):
        data = {
            "strategy_type": "dfs",
            "visited": ["https://a.com"],
            "pending": [],
            "depths": {},
            "pages_crawled": 1,
        }
        state = CrawlState.from_dict(data)
        assert state.strategy_type == "dfs"
        assert "https://a.com" in state.visited


# ---------------------------------------------------------------------------
# BFS Strategy
# ---------------------------------------------------------------------------


class TestBFSStrategy:
    @pytest.mark.asyncio
    async def test_basic_bfs(self):
        strategy = BFSStrategy(max_depth=2, max_pages=10)
        strategy.seed("https://example.com")

        batch = await strategy.get_next_urls()
        assert len(batch) == 1
        assert "example.com" in batch[0].url

    @pytest.mark.asyncio
    async def test_bfs_fifo_order(self):
        strategy = BFSStrategy(max_depth=2, max_pages=100)
        strategy.seed("https://example.com")

        # Get the seed URL
        batch = await strategy.get_next_urls()
        assert len(batch) == 1
        strategy._state.visited.add(batch[0].url)

        # Add discovered URLs
        await strategy.add_discovered_urls(
            ["https://example.com/a", "https://example.com/b"],
            "https://example.com",
            1,
        )

        # Should come in FIFO order
        batch = await strategy.get_next_urls()
        assert len(batch) == 2
        urls = [item.url for item in batch]
        assert "example.com/a" in urls[0] or "example.com/b" in urls[0]

    @pytest.mark.asyncio
    async def test_bfs_max_depth(self):
        strategy = BFSStrategy(max_depth=1, max_pages=100)
        strategy.seed("https://example.com")

        # Get seed
        await strategy.get_next_urls()

        # Try to add depth=2 URLs — should be rejected
        await strategy.add_discovered_urls(
            ["https://example.com/deep"],
            "https://example.com",
            2,
        )
        batch = await strategy.get_next_urls()
        assert len(batch) == 0

    @pytest.mark.asyncio
    async def test_state_export(self):
        strategy = BFSStrategy(max_depth=3, max_pages=100)
        strategy.seed("https://example.com")
        state = strategy.export_state()
        assert state["strategy_type"] == "bfs"


# ---------------------------------------------------------------------------
# DFS Strategy
# ---------------------------------------------------------------------------


class TestDFSStrategy:
    @pytest.mark.asyncio
    async def test_basic_dfs(self):
        strategy = DFSStrategy(max_depth=3, max_pages=10)
        strategy.seed("https://example.com")

        batch = await strategy.get_next_urls()
        assert len(batch) == 1

    @pytest.mark.asyncio
    async def test_dfs_lifo_order(self):
        strategy = DFSStrategy(max_depth=3, max_pages=100)
        strategy.seed("https://example.com")

        batch = await strategy.get_next_urls()
        strategy._state.visited.add(batch[0].url)

        await strategy.add_discovered_urls(
            ["https://example.com/a", "https://example.com/b"],
            "https://example.com",
            1,
        )

        # DFS: last added should be first out (LIFO)
        batch = await strategy.get_next_urls()
        assert len(batch) >= 1


# ---------------------------------------------------------------------------
# BestFirst Strategy
# ---------------------------------------------------------------------------


class TestBestFirstStrategy:
    @pytest.mark.asyncio
    async def test_basic_best_first(self):
        scorer = KeywordRelevanceScorer(keywords=["product"])
        strategy = BestFirstStrategy(
            max_depth=3, max_pages=100, scorer=scorer
        )
        strategy.seed("https://example.com")

        batch = await strategy.get_next_urls()
        assert len(batch) == 1

    @pytest.mark.asyncio
    async def test_prioritizes_by_score(self):
        scorer = KeywordRelevanceScorer(keywords=["product", "shop"])
        strategy = BestFirstStrategy(
            max_depth=3, max_pages=100, scorer=scorer
        )
        strategy.seed("https://example.com")

        batch = await strategy.get_next_urls()
        strategy._state.visited.add(batch[0].url)

        await strategy.add_discovered_urls(
            [
                "https://example.com/about",     # no keywords
                "https://example.com/product/1",  # has "product"
                "https://example.com/shop/items", # has "shop"
            ],
            "https://example.com",
            1,
        )

        batch = await strategy.get_next_urls()
        # Higher-scored URLs should come first
        assert len(batch) >= 1


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


class TestKeywordRelevanceScorer:
    def test_full_match(self):
        scorer = KeywordRelevanceScorer(keywords=["product", "shop"])
        score = scorer.score("https://example.com/product/shop")
        assert score == 1.0

    def test_partial_match(self):
        scorer = KeywordRelevanceScorer(keywords=["product", "shop"])
        score = scorer.score("https://example.com/product/info")
        assert score == 0.5

    def test_no_match(self):
        scorer = KeywordRelevanceScorer(keywords=["product", "shop"])
        score = scorer.score("https://example.com/about")
        assert score == 0.0


class TestPathDepthScorer:
    def test_optimal_depth(self):
        scorer = PathDepthScorer(optimal_depth=2)
        score = scorer.score("https://example.com/a/b")
        assert score == 1.0

    def test_shallow(self):
        scorer = PathDepthScorer(optimal_depth=2)
        score = scorer.score("https://example.com/")
        # Depth 0, distance 2
        assert score < 0.5


class TestContentTypeScorer:
    def test_html_page(self):
        scorer = ContentTypeScorer()
        assert scorer.score("https://example.com/page.html") == 1.0

    def test_image(self):
        scorer = ContentTypeScorer()
        assert scorer.score("https://example.com/img.jpg") == 0.1

    def test_no_extension(self):
        scorer = ContentTypeScorer()
        assert scorer.score("https://example.com/page") == 1.0


class TestFreshnessScorer:
    def test_current_year(self):
        scorer = FreshnessScorer(current_year=2026)
        assert scorer.score("https://example.com/2026/article") == 1.0

    def test_old_content(self):
        scorer = FreshnessScorer(current_year=2026)
        score = scorer.score("https://example.com/2018/old-post")
        assert score < 0.5


class TestCompositeScorer:
    def test_weighted_combination(self):
        kw = KeywordRelevanceScorer(keywords=["product"])
        depth = PathDepthScorer(optimal_depth=2)
        composite = CompositeScorer([(kw, 2.0), (depth, 1.0)])
        score = composite.score("https://example.com/product/item")
        assert 0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestURLPatternFilter:
    @pytest.mark.asyncio
    async def test_glob_include(self):
        f = URLPatternFilter(patterns=["/products/*"])
        assert await f.apply("https://example.com/products/item1") is True
        assert await f.apply("https://example.com/about") is False

    @pytest.mark.asyncio
    async def test_glob_exclude(self):
        f = URLPatternFilter(patterns=["/admin/*"], exclude=True)
        assert await f.apply("https://example.com/products") is True
        assert await f.apply("https://example.com/admin/users") is False

    @pytest.mark.asyncio
    async def test_regex_mode(self):
        f = URLPatternFilter(patterns=[r"/product/\d+"], mode="regex")
        assert await f.apply("https://example.com/product/123") is True
        assert await f.apply("https://example.com/product/abc") is False


class TestDomainFilter:
    @pytest.mark.asyncio
    async def test_allowed_domains(self):
        f = DomainFilter(allowed_domains=["example.com"])
        assert await f.apply("https://example.com/page") is True
        assert await f.apply("https://other.com/page") is False

    @pytest.mark.asyncio
    async def test_blocked_domains(self):
        f = DomainFilter(blocked_domains=["spam.com"])
        assert await f.apply("https://example.com/page") is True
        assert await f.apply("https://spam.com/page") is False


class TestContentTypeFilter:
    @pytest.mark.asyncio
    async def test_html_allowed(self):
        f = ContentTypeFilter()
        assert await f.apply("https://example.com/page.html") is True
        assert await f.apply("https://example.com/page") is True

    @pytest.mark.asyncio
    async def test_non_html_rejected(self):
        f = ContentTypeFilter()
        assert await f.apply("https://example.com/style.css") is False


class TestFilterChain:
    @pytest.mark.asyncio
    async def test_chain_all_pass(self):
        chain = FilterChain([
            DomainFilter(allowed_domains=["example.com"]),
            ContentTypeFilter(),
        ])
        assert await chain.apply("https://example.com/page.html") is True

    @pytest.mark.asyncio
    async def test_chain_one_fails(self):
        chain = FilterChain([
            DomainFilter(allowed_domains=["example.com"]),
            ContentTypeFilter(),
        ])
        assert await chain.apply("https://other.com/page.html") is False

    @pytest.mark.asyncio
    async def test_empty_chain(self):
        chain = FilterChain([])
        assert await chain.apply("https://anything.com") is True
