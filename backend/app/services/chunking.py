"""Text chunking strategies for LLM processing."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


class ChunkingStrategy(ABC):
    """Base class for text chunking."""

    @abstractmethod
    def chunk(self, text: str) -> list[str]:
        """Split text into chunks."""
        ...


class RegexChunking(ChunkingStrategy):
    """Split text by regex pattern (default: double newline for paragraphs)."""

    def __init__(self, patterns: list[str] | None = None):
        self._patterns = patterns or [r"\n\n"]

    def chunk(self, text: str) -> list[str]:
        chunks = [text]
        for pattern in self._patterns:
            new_chunks = []
            for c in chunks:
                parts = re.split(pattern, c)
                new_chunks.extend(p.strip() for p in parts if p.strip())
            chunks = new_chunks
        return chunks


class FixedLengthWordChunking(ChunkingStrategy):
    """Split into fixed word-count chunks."""

    def __init__(self, chunk_size: int = 100):
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), self.chunk_size):
            chunk = " ".join(words[i : i + self.chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks


class SlidingWindowChunking(ChunkingStrategy):
    """Sliding window with configurable overlap."""

    def __init__(self, window_size: int = 100, step: int = 50):
        self.window_size = window_size
        self.step = step

    def chunk(self, text: str) -> list[str]:
        words = text.split()
        if len(words) <= self.window_size:
            return [text] if text.strip() else []
        chunks = []
        for i in range(0, len(words) - self.window_size + 1, self.step):
            chunk = " ".join(words[i : i + self.window_size])
            chunks.append(chunk)
        # Ensure last words are included
        if chunks and i + self.window_size < len(words):
            chunks.append(" ".join(words[-self.window_size :]))
        return chunks


class OverlappingWindowChunking(ChunkingStrategy):
    """Fixed window with explicit overlap word count."""

    def __init__(self, window_size: int = 1000, overlap: int = 100):
        self.window_size = window_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        step = max(1, self.window_size - self.overlap)
        words = text.split()
        if len(words) <= self.window_size:
            return [text] if text.strip() else []
        chunks = []
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + self.window_size])
            if chunk:
                chunks.append(chunk)
            if i + self.window_size >= len(words):
                break
        return chunks


class SentenceChunking(ChunkingStrategy):
    """Split by sentence boundaries."""

    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def chunk(self, text: str) -> list[str]:
        sentences = self._SENTENCE_RE.split(text)
        return [s.strip() for s in sentences if s.strip()]


class TopicChunking(ChunkingStrategy):
    """Split by heading boundaries (Markdown-aware)."""

    _HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)

    def chunk(self, text: str) -> list[str]:
        parts = self._HEADING_RE.split(text)
        # Re-attach headings
        headings = self._HEADING_RE.findall(text)
        chunks = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            if i > 0 and i - 1 < len(headings):
                part = headings[i - 1] + part
            chunks.append(part)
        return chunks if chunks else [text]
