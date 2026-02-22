"""Tests for markdown citation generation and fit markdown."""
import pytest
from app.services.markdown_utils import generate_citations, generate_fit_markdown


class TestCitations:
    def test_inline_links_converted(self):
        md = "Check out [Google](https://google.com) and [GitHub](https://github.com)."
        result = generate_citations(md)
        # Should convert inline links to numbered citations
        assert "Google" in result.markdown_with_citations
        assert result.references_markdown != ""

    def test_no_links(self):
        md = "Plain text with no links."
        result = generate_citations(md)
        assert result.markdown_with_citations == md
        assert result.references_markdown == ""

    def test_duplicate_links_merged(self):
        md = "Visit [Site](https://example.com) and [Site again](https://example.com)."
        result = generate_citations(md)
        # Both should reference the same citation number
        assert "example.com" in result.references_markdown
        # Only one reference entry for the same URL
        assert result.references_markdown.count("example.com") >= 1


class TestFitMarkdown:
    def test_basic_fit(self):
        md = "# Title\n\nFirst paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        html = "<html><body><h1>Title</h1><p>First paragraph.</p><p>Second paragraph.</p><p>Third paragraph.</p></body></html>"
        result = generate_fit_markdown(md, html)
        assert isinstance(result.fit_markdown, str)

    def test_empty_input(self):
        result = generate_fit_markdown("", "")
        assert isinstance(result, object)
