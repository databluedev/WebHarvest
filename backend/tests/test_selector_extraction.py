"""Tests for CSS/XPath selector extraction."""
import pytest
from app.services.selector_extraction import extract_by_css, extract_by_xpath, extract_by_selectors

SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
    <h1 class="title">Product Title</h1>
    <div class="product">
        <span class="price">$29.99</span>
        <span class="brand">TestBrand</span>
        <p class="desc">A great product for testing.</p>
        <a href="/buy" class="buy-btn">Buy Now</a>
    </div>
    <ul class="features">
        <li>Feature 1</li>
        <li>Feature 2</li>
        <li>Feature 3</li>
    </ul>
    <table>
        <tr><th>Size</th><th>Price</th></tr>
        <tr><td>S</td><td>$25</td></tr>
        <tr><td>M</td><td>$30</td></tr>
    </table>
</body>
</html>
"""


class TestCSSExtraction:
    def test_extract_text_by_css(self):
        result = extract_by_css(SAMPLE_HTML, "h1.title")
        assert result == ["Product Title"]

    def test_extract_multiple_elements(self):
        result = extract_by_css(SAMPLE_HTML, "ul.features li")
        assert result == ["Feature 1", "Feature 2", "Feature 3"]

    def test_extract_html_by_css(self):
        result = extract_by_css(SAMPLE_HTML, "span.price", extract_type="html")
        assert len(result) == 1
        assert "$29.99" in result[0]
        assert "<span" in result[0]

    def test_extract_attribute(self):
        result = extract_by_css(SAMPLE_HTML, "a.buy-btn", extract_type="href")
        assert result == ["/buy"]

    def test_no_match_returns_empty(self):
        result = extract_by_css(SAMPLE_HTML, "div.nonexistent")
        assert result == []

    def test_nested_selector(self):
        result = extract_by_css(SAMPLE_HTML, "div.product span.price")
        assert result == ["$29.99"]


class TestXPathExtraction:
    def test_extract_text_by_xpath(self):
        result = extract_by_xpath(SAMPLE_HTML, "//h1[@class='title']/text()")
        assert result == ["Product Title"]

    def test_extract_attribute_by_xpath(self):
        result = extract_by_xpath(SAMPLE_HTML, "//a[@class='buy-btn']/@href")
        assert result == ["/buy"]

    def test_extract_multiple_by_xpath(self):
        result = extract_by_xpath(SAMPLE_HTML, "//ul[@class='features']/li/text()")
        assert result == ["Feature 1", "Feature 2", "Feature 3"]

    def test_invalid_xpath_returns_empty(self):
        result = extract_by_xpath(SAMPLE_HTML, "///invalid[")
        assert result == []

    def test_element_text_extraction(self):
        result = extract_by_xpath(SAMPLE_HTML, "//div[@class='product']/span[@class='brand']")
        assert len(result) == 1
        assert "TestBrand" in result[0]


class TestMultipleSelectors:
    def test_extract_by_selectors(self):
        selectors = {
            "title": {"css": "h1.title", "type": "text"},
            "price": {"css": "span.price", "type": "text"},
            "link": {"css": "a.buy-btn", "type": "href"},
            "features": {"xpath": "//ul[@class='features']/li/text()"},
        }
        result = extract_by_selectors(SAMPLE_HTML, selectors)
        assert result["title"] == ["Product Title"]
        assert result["price"] == ["$29.99"]
        assert result["link"] == ["/buy"]
        assert result["features"] == ["Feature 1", "Feature 2", "Feature 3"]

    def test_empty_selectors(self):
        result = extract_by_selectors(SAMPLE_HTML, {})
        assert result == {}
