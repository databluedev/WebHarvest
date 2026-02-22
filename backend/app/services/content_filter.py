"""Content filtering strategies — BM25 relevance and pruning-based."""

from __future__ import annotations

import math
import re
import logging
from abc import ABC, abstractmethod
from collections import Counter

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class ContentFilter(ABC):
    """Base class for content relevance filtering."""

    @abstractmethod
    def filter_content(self, html: str, query: str | None = None) -> str:
        """Filter HTML to keep only relevant content blocks.

        Returns filtered HTML string.
        """
        ...


def _extract_text_blocks(html: str, min_words: int = 5) -> list[dict]:
    """Extract text blocks from HTML with their tags and text."""
    soup = BeautifulSoup(html, "lxml")
    blocks = []

    # Content tags to consider
    content_tags = {"p", "div", "section", "article", "main", "li", "td",
                    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"}
    # Tags to skip
    skip_tags = {"nav", "footer", "header", "aside", "form", "script", "style", "noscript"}

    for tag in soup.find_all(content_tags):
        # Skip if inside a skip tag
        if any(parent.name in skip_tags for parent in tag.parents if isinstance(parent, Tag)):
            continue
        text = tag.get_text(strip=True)
        words = text.split()
        if len(words) >= min_words:
            blocks.append({
                "tag": tag,
                "text": text,
                "words": words,
                "tag_name": tag.name,
            })
    return blocks


def _extract_page_query(html: str) -> str:
    """Extract a query from the page itself (title + h1 + meta description)."""
    soup = BeautifulSoup(html, "lxml")
    parts = []

    title = soup.find("title")
    if title:
        parts.append(title.get_text(strip=True))

    h1 = soup.find("h1")
    if h1:
        parts.append(h1.get_text(strip=True))

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        parts.append(meta_desc.get("content", ""))

    return " ".join(parts)


# Simple English stop words
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "it", "its", "not", "no", "so", "if", "as",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, removing stop words."""
    words = re.findall(r"\b[a-z]+\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


class BM25ContentFilter(ContentFilter):
    """Filter content blocks by BM25 Okapi relevance scoring.

    Uses page metadata (title, h1, description) as query if none provided.
    """

    def __init__(
        self,
        threshold: float = 1.0,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.threshold = threshold
        self.k1 = k1
        self.b = b

    # Tag priority weights
    _TAG_WEIGHTS = {
        "h1": 5.0, "h2": 4.0, "h3": 3.0, "h4": 2.5,
        "h5": 2.0, "h6": 1.5,
        "strong": 2.0, "b": 1.5, "em": 1.5,
        "blockquote": 2.0, "pre": 1.5, "code": 1.5,
    }

    def filter_content(self, html: str, query: str | None = None) -> str:
        if not query:
            query = _extract_page_query(html)
        if not query:
            return html  # Can't filter without a query

        blocks = _extract_text_blocks(html)
        if not blocks:
            return html

        query_tokens = _tokenize(query)
        if not query_tokens:
            return html

        # Build corpus stats
        doc_count = len(blocks)
        avg_dl = sum(len(b["words"]) for b in blocks) / max(doc_count, 1)

        # Document frequency for each query term
        df: Counter = Counter()
        for block in blocks:
            block_tokens = set(_tokenize(block["text"]))
            for qt in query_tokens:
                if qt in block_tokens:
                    df[qt] += 1

        # Score each block
        scored_blocks = []
        for block in blocks:
            block_tokens = _tokenize(block["text"])
            tf = Counter(block_tokens)
            dl = len(block["words"])

            score = 0.0
            for qt in query_tokens:
                if qt not in tf:
                    continue
                # IDF
                n = df.get(qt, 0)
                idf = math.log((doc_count - n + 0.5) / (n + 0.5) + 1.0)
                # TF with BM25 normalization
                freq = tf[qt]
                tf_norm = (freq * (self.k1 + 1)) / (freq + self.k1 * (1 - self.b + self.b * dl / avg_dl))
                score += idf * tf_norm

            # Apply tag weight boost
            tag_weight = self._TAG_WEIGHTS.get(block["tag_name"], 1.0)
            score *= tag_weight

            scored_blocks.append((block, score))

        # Keep blocks above threshold
        kept_tags = set()
        for block, score in scored_blocks:
            if score >= self.threshold:
                kept_tags.add(id(block["tag"]))

        if not kept_tags:
            return html  # Nothing scored high enough, return all

        # Rebuild filtered HTML
        soup = BeautifulSoup(html, "lxml")
        filtered_parts = []
        for block, score in scored_blocks:
            if id(block["tag"]) in kept_tags:
                filtered_parts.append(str(block["tag"]))

        return "\n".join(filtered_parts)


class PruningContentFilter(ContentFilter):
    """Filter using composite metrics — text density, link density, tag weight."""

    def __init__(self, threshold: float = 0.48):
        self.threshold = threshold

    def filter_content(self, html: str, query: str | None = None) -> str:
        blocks = _extract_text_blocks(html, min_words=2)
        if not blocks:
            return html

        scored = []
        for block in blocks:
            text = block["text"]
            tag = block["tag"]

            # Text density: text length / total tag HTML length
            tag_html = str(tag)
            text_density = len(text) / max(len(tag_html), 1)

            # Link density: 1 - (link_text / total_text)
            link_text = "".join(a.get_text() for a in tag.find_all("a"))
            link_density = 1.0 - (len(link_text) / max(len(text), 1))

            # Tag weight
            tag_weights = {"article": 1.0, "main": 1.0, "section": 0.8,
                          "p": 0.7, "div": 0.5, "li": 0.6, "td": 0.4}
            tag_weight = tag_weights.get(block["tag_name"], 0.5)

            # Text length score (log-based)
            text_len_score = min(1.0, math.log(max(len(text), 1)) / 10.0)

            # Composite score
            score = (
                0.4 * text_density
                + 0.2 * link_density
                + 0.2 * tag_weight
                + 0.2 * text_len_score
            )
            scored.append((block, score))

        # Keep blocks above threshold
        filtered_parts = []
        for block, score in scored:
            if score >= self.threshold:
                filtered_parts.append(str(block["tag"]))

        return "\n".join(filtered_parts) if filtered_parts else html
