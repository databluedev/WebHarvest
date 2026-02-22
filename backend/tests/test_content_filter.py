"""Tests for BM25 and pruning content filters."""
import pytest
from app.services.content_filter import BM25ContentFilter, PruningContentFilter

SAMPLE_HTML = """
<html>
<head><title>Python Web Development</title></head>
<body>
<h1>Python Web Development Guide</h1>
<p>Python is a programming language used for web development and is very popular among developers worldwide.</p>
<p>The weather today is sunny and warm and has nothing to do with programming at all really.</p>
<p>Django and Flask are popular Python web frameworks used by thousands of developers for building applications.</p>
<p>Cats and dogs are common household pets that many people enjoy having around the house every day.</p>
<p>Machine learning uses Python extensively for data science applications and artificial intelligence research.</p>
</body>
</html>
"""


class TestBM25ContentFilter:
    def test_relevance_ranking(self):
        filt = BM25ContentFilter()
        result = filt.filter_content(SAMPLE_HTML, query="Python web development")
        # Should prioritize Python-related paragraphs
        assert "Python" in result

    def test_empty_text(self):
        filt = BM25ContentFilter()
        assert filt.filter_content("") == ""

    def test_no_query_uses_page_metadata(self):
        filt = BM25ContentFilter()
        # Without query, should use page title/h1 as query
        result = filt.filter_content(SAMPLE_HTML)
        assert isinstance(result, str)


class TestPruningContentFilter:
    def test_removes_low_content_blocks(self):
        filt = PruningContentFilter(threshold=0.3)
        html_text = """
        <html><body>
        <article>
        <p>Important article content with many words about the topic that is very relevant.</p>
        </article>
        <div class="sidebar"><span>Ad</span></div>
        <article>
        <p>More substantive content about the main topic of discussion that readers care about.</p>
        </article>
        <footer>Copyright 2024</footer>
        </body></html>
        """
        result = filt.filter_content(html_text)
        assert isinstance(result, str)

    def test_empty_input(self):
        filt = PruningContentFilter()
        assert filt.filter_content("") == ""
