"""URL scoring strategies for Best-First crawling."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse


class URLScorer(ABC):
    """Base class for URL scoring."""

    @abstractmethod
    def score(self, url: str) -> float:
        """Score a URL from 0.0 (irrelevant) to 1.0 (highly relevant)."""
        ...


class KeywordRelevanceScorer(URLScorer):
    """Score URLs by keyword presence in the URL string."""

    def __init__(self, keywords: list[str], case_sensitive: bool = False):
        self.keywords = keywords
        self.case_sensitive = case_sensitive

    def score(self, url: str) -> float:
        target = url if self.case_sensitive else url.lower()
        matched = sum(
            1 for kw in self.keywords
            if (kw if self.case_sensitive else kw.lower()) in target
        )
        return matched / len(self.keywords) if self.keywords else 0.0


class PathDepthScorer(URLScorer):
    """Score URLs by path depth — prefer optimal depth."""

    def __init__(self, optimal_depth: int = 2):
        self.optimal_depth = optimal_depth

    def score(self, url: str) -> float:
        try:
            parsed = urlparse(url)
            segments = [s for s in parsed.path.strip("/").split("/") if s]
            depth = len(segments)
            distance = abs(depth - self.optimal_depth)
            return 1.0 / (1.0 + distance)
        except Exception:
            return 0.5


class ContentTypeScorer(URLScorer):
    """Score URLs by file extension — prefer HTML content."""

    _WEIGHTS = {
        ".html": 1.0, ".htm": 1.0, "": 1.0,  # no extension = likely HTML
        ".php": 0.9, ".asp": 0.9, ".aspx": 0.9, ".jsp": 0.9,
        ".pdf": 0.7, ".doc": 0.5, ".docx": 0.5,
        ".xml": 0.6, ".json": 0.6,
        ".jpg": 0.1, ".png": 0.1, ".gif": 0.1, ".svg": 0.1,
        ".css": 0.0, ".js": 0.0, ".zip": 0.0,
    }

    def score(self, url: str) -> float:
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            for ext, weight in self._WEIGHTS.items():
                if ext and path.endswith(ext):
                    return weight
            return 1.0  # No extension = likely HTML page
        except Exception:
            return 0.5


class FreshnessScorer(URLScorer):
    """Score URLs by date patterns in the URL — prefer recent content."""

    _YEAR_PATTERN = re.compile(r"(20[12]\d)")

    def __init__(self, current_year: int = 2026):
        self.current_year = current_year

    def score(self, url: str) -> float:
        match = self._YEAR_PATTERN.search(url)
        if not match:
            return 0.5  # Unknown age
        year = int(match.group(1))
        age = self.current_year - year
        if age <= 0:
            return 1.0
        if age <= 1:
            return 0.9
        if age <= 2:
            return 0.7
        if age <= 5:
            return 0.4
        return 0.2


class CompositeScorer(URLScorer):
    """Combine multiple scorers with weights."""

    def __init__(self, scorers: list[tuple[URLScorer, float]]):
        self.scorers = scorers
        total_weight = sum(w for _, w in scorers)
        self._norm = total_weight if total_weight > 0 else 1.0

    def score(self, url: str) -> float:
        total = sum(scorer.score(url) * weight for scorer, weight in self.scorers)
        return total / self._norm
