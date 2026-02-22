"""URL filters for deep crawling — pattern, domain, content type."""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse


class URLFilter(ABC):
    """Base class for URL filters."""

    @abstractmethod
    async def apply(self, url: str) -> bool:
        """Return True if the URL should be kept, False to reject."""
        ...


class FilterChain:
    """Chain of URL filters — rejects on first failure (AND logic)."""

    def __init__(self, filters: list[URLFilter] | None = None):
        self.filters = filters or []

    async def apply(self, url: str) -> bool:
        for f in self.filters:
            if not await f.apply(url):
                return False
        return True


class URLPatternFilter(URLFilter):
    """Filter URLs by glob or regex patterns."""

    def __init__(
        self,
        patterns: list[str],
        mode: str = "glob",
        exclude: bool = False,
    ):
        self.exclude = exclude
        self.mode = mode
        if mode == "regex":
            self._compiled = [re.compile(p) for p in patterns]
        else:
            self._patterns = patterns

    async def apply(self, url: str) -> bool:
        if self.mode == "regex":
            matched = any(r.search(url) for r in self._compiled)
        else:
            path = urlparse(url).path
            matched = any(fnmatch.fnmatch(path, p) for p in self._patterns)
        return not matched if self.exclude else matched


class DomainFilter(URLFilter):
    """Filter URLs by allowed/blocked domain lists."""

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ):
        self._allowed = frozenset(d.lower() for d in (allowed_domains or []))
        self._blocked = frozenset(d.lower() for d in (blocked_domains or []))

    async def apply(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return False
        if self._blocked and domain in self._blocked:
            return False
        if self._allowed and domain not in self._allowed:
            return False
        return True


class ContentTypeFilter(URLFilter):
    """Filter by file extension (content type proxy)."""

    _PAGE_EXTENSIONS = {
        "", ".html", ".htm", ".php", ".asp", ".aspx", ".jsp",
        ".shtml", ".xhtml",
    }

    def __init__(self, allowed_types: str = "text/html"):
        self._allow_pages = "html" in allowed_types.lower()

    async def apply(self, url: str) -> bool:
        try:
            path = urlparse(url).path.lower()
            # Get extension
            dot_idx = path.rfind(".")
            ext = path[dot_idx:] if dot_idx > 0 else ""
            return ext in self._PAGE_EXTENSIONS
        except Exception:
            return True
