"""Tests for text chunking strategies."""
import pytest
from app.services.chunking import (
    RegexChunking,
    FixedLengthWordChunking,
    SlidingWindowChunking,
    OverlappingWindowChunking,
    SentenceChunking,
)

SAMPLE_TEXT = """First paragraph with some content here.

Second paragraph with different content.

Third paragraph is the final one."""

LONG_TEXT = " ".join(f"word{i}" for i in range(100))


class TestRegexChunking:
    def test_default_split_on_paragraphs(self):
        chunker = RegexChunking()
        chunks = chunker.chunk(SAMPLE_TEXT)
        assert len(chunks) >= 2
        assert any("First paragraph" in c for c in chunks)

    def test_custom_pattern(self):
        chunker = RegexChunking(patterns=[r"\. "])
        text = "Sentence one. Sentence two. Sentence three."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2


class TestFixedLengthWordChunking:
    def test_basic_chunking(self):
        chunker = FixedLengthWordChunking(chunk_size=20)
        chunks = chunker.chunk(LONG_TEXT)
        assert len(chunks) >= 4
        for chunk in chunks:
            words = chunk.split()
            assert len(words) <= 20

    def test_single_chunk_if_short(self):
        chunker = FixedLengthWordChunking(chunk_size=200)
        chunks = chunker.chunk("Short text")
        assert len(chunks) == 1


class TestSlidingWindowChunking:
    def test_overlapping_windows(self):
        chunker = SlidingWindowChunking(window_size=30, step=20)
        chunks = chunker.chunk(LONG_TEXT)
        assert len(chunks) >= 3
        # Chunks should overlap
        words_1 = set(chunks[0].split())
        words_2 = set(chunks[1].split())
        assert len(words_1 & words_2) > 0


class TestOverlappingWindowChunking:
    def test_overlap(self):
        chunker = OverlappingWindowChunking(window_size=30, overlap=10)
        chunks = chunker.chunk(LONG_TEXT)
        assert len(chunks) >= 2


class TestSentenceChunking:
    def test_sentence_split(self):
        text = "This is sentence one. This is sentence two. And sentence three."
        chunker = SentenceChunking()
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
