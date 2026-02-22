"""Crawl traversal strategies — BFS, DFS, Best-First."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from urllib.parse import urlparse

from app.services.deep_crawl.filters import FilterChain
from app.services.deep_crawl.scorers import URLScorer

logger = logging.getLogger(__name__)


@dataclass(order=True)
class CrawlURL:
    """A URL in the crawl frontier with metadata."""
    url: str
    depth: int = 0
    parent_url: str | None = field(default=None, compare=False)
    score: float = 0.0


@dataclass
class CrawlState:
    """Serializable crawl state for checkpoint/resume."""
    strategy_type: str = "bfs"
    visited: set[str] = field(default_factory=set)
    pending: list[dict] = field(default_factory=list)
    depths: dict[str, int] = field(default_factory=dict)
    pages_crawled: int = 0

    def to_dict(self) -> dict:
        return {
            "strategy_type": self.strategy_type,
            "visited": list(self.visited),
            "pending": self.pending,
            "depths": self.depths,
            "pages_crawled": self.pages_crawled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CrawlState:
        state = cls(
            strategy_type=data.get("strategy_type", "bfs"),
            visited=set(data.get("visited", [])),
            pending=data.get("pending", []),
            depths=data.get("depths", {}),
            pages_crawled=data.get("pages_crawled", 0),
        )
        return state


class DeepCrawlStrategy(ABC):
    """Base class for deep crawl traversal strategies."""

    def __init__(
        self,
        max_depth: int = 3,
        max_pages: int = 100,
        filter_chain: FilterChain | None = None,
        scorer: URLScorer | None = None,
        score_threshold: float = float("-inf"),
        include_external: bool = False,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.filter_chain = filter_chain or FilterChain([])
        self.scorer = scorer
        self.score_threshold = score_threshold
        self.include_external = include_external
        self._state = CrawlState(strategy_type=self.__class__.__name__.lower().replace("strategy", ""))
        self._base_domain: str = ""

    @property
    def state(self) -> CrawlState:
        return self._state

    def export_state(self) -> dict:
        """Export current crawl state for checkpointing."""
        return self._state.to_dict()

    def restore_state(self, state_data: dict) -> None:
        """Restore crawl state from a checkpoint."""
        self._state = CrawlState.from_dict(state_data)

    def _normalize_url(self, url: str) -> str:
        """Minimal normalization for dedup."""
        from app.services.dedup import normalize_url
        return normalize_url(url)

    def _is_same_domain(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain == self._base_domain
        except Exception:
            return False

    async def filter_url(self, url: str) -> bool:
        """Check if URL passes the filter chain."""
        if self.filter_chain:
            return await self.filter_chain.apply(url)
        return True

    def score_url(self, url: str) -> float:
        """Score a URL for prioritization."""
        if self.scorer:
            return self.scorer.score(url)
        return 0.0

    @abstractmethod
    async def get_next_urls(self) -> list[CrawlURL]:
        """Get the next batch of URLs to crawl."""
        ...

    @abstractmethod
    async def add_discovered_urls(
        self, urls: list[str], parent_url: str, depth: int
    ) -> None:
        """Add newly discovered URLs to the frontier."""
        ...

    async def _process_discovered(
        self, urls: list[str], parent_url: str, depth: int
    ) -> list[CrawlURL]:
        """Filter, score, and dedup discovered URLs."""
        results = []
        for url in urls:
            norm = self._normalize_url(url)
            if norm in self._state.visited:
                continue
            if not self.include_external and not self._is_same_domain(url):
                continue
            if not await self.filter_url(url):
                continue
            score = self.score_url(url)
            if score < self.score_threshold:
                continue
            results.append(CrawlURL(
                url=norm, depth=depth, parent_url=parent_url, score=score
            ))
        return results


class BFSStrategy(DeepCrawlStrategy):
    """Breadth-first crawl — process level by level."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._queue: deque[CrawlURL] = deque()
        self._state.strategy_type = "bfs"

    async def get_next_urls(self) -> list[CrawlURL]:
        batch = []
        while self._queue and len(batch) < 10:
            item = self._queue.popleft()
            if item.url in self._state.visited:
                continue
            if self._state.pages_crawled >= self.max_pages:
                break
            batch.append(item)
        return batch

    async def add_discovered_urls(
        self, urls: list[str], parent_url: str, depth: int
    ) -> None:
        if depth > self.max_depth:
            return
        processed = await self._process_discovered(urls, parent_url, depth)
        for item in processed:
            self._queue.append(item)

    def seed(self, start_url: str):
        """Seed the BFS queue with the start URL."""
        parsed = urlparse(start_url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        self._base_domain = domain
        norm = self._normalize_url(start_url)
        self._queue.append(CrawlURL(url=norm, depth=0))


class DFSStrategy(DeepCrawlStrategy):
    """Depth-first crawl — explore branches fully before backtracking."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stack: list[CrawlURL] = []
        self._state.strategy_type = "dfs"

    async def get_next_urls(self) -> list[CrawlURL]:
        batch = []
        while self._stack and len(batch) < 10:
            item = self._stack.pop()  # LIFO
            if item.url in self._state.visited:
                continue
            if self._state.pages_crawled >= self.max_pages:
                break
            batch.append(item)
        return batch

    async def add_discovered_urls(
        self, urls: list[str], parent_url: str, depth: int
    ) -> None:
        if depth > self.max_depth:
            return
        processed = await self._process_discovered(urls, parent_url, depth)
        # Add in reverse so first link is on top of stack
        for item in reversed(processed):
            self._stack.append(item)

    def seed(self, start_url: str):
        parsed = urlparse(start_url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        self._base_domain = domain
        norm = self._normalize_url(start_url)
        self._stack.append(CrawlURL(url=norm, depth=0))


class BestFirstStrategy(DeepCrawlStrategy):
    """Best-first crawl — prioritize by score (highest first)."""

    def __init__(self, batch_size: int = 10, **kwargs):
        super().__init__(**kwargs)
        self._pqueue: list[tuple[float, CrawlURL]] = []
        self._batch_size = batch_size
        self._state.strategy_type = "bff"

    async def get_next_urls(self) -> list[CrawlURL]:
        import heapq
        batch = []
        while self._pqueue and len(batch) < self._batch_size:
            neg_score, item = heapq.heappop(self._pqueue)
            if item.url in self._state.visited:
                continue
            if self._state.pages_crawled >= self.max_pages:
                break
            batch.append(item)
        return batch

    async def add_discovered_urls(
        self, urls: list[str], parent_url: str, depth: int
    ) -> None:
        import heapq
        if depth > self.max_depth:
            return
        processed = await self._process_discovered(urls, parent_url, depth)
        for item in processed:
            # Negate score for min-heap (highest score = lowest negative)
            heapq.heappush(self._pqueue, (-item.score, item))

    def seed(self, start_url: str):
        import heapq
        parsed = urlparse(start_url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        self._base_domain = domain
        norm = self._normalize_url(start_url)
        item = CrawlURL(url=norm, depth=0, score=1.0)
        heapq.heappush(self._pqueue, (-1.0, item))
