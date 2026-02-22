"""Deep crawling strategies — BFS, DFS, Best-First with scoring and filtering."""

from app.services.deep_crawl.strategies import BFSStrategy, DFSStrategy, BestFirstStrategy
from app.services.deep_crawl.scorers import (
    URLScorer,
    CompositeScorer,
    KeywordRelevanceScorer,
    PathDepthScorer,
    ContentTypeScorer,
    FreshnessScorer,
)
from app.services.deep_crawl.filters import (
    URLFilter,
    FilterChain,
    URLPatternFilter,
    DomainFilter,
    ContentTypeFilter,
)

__all__ = [
    "BFSStrategy", "DFSStrategy", "BestFirstStrategy",
    "URLScorer", "CompositeScorer", "KeywordRelevanceScorer",
    "PathDepthScorer", "ContentTypeScorer", "FreshnessScorer",
    "URLFilter", "FilterChain", "URLPatternFilter",
    "DomainFilter", "ContentTypeFilter",
]
