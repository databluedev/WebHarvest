"""CSS and XPath selector-based content extraction.

Allows users to specify CSS selectors or XPath expressions to extract
specific parts of a page, similar to Crawl4AI's css_selector and
xpath support.
"""
from __future__ import annotations
import logging
from typing import Any
from bs4 import BeautifulSoup
from lxml import etree

logger = logging.getLogger(__name__)


def extract_by_css(html: str, selector: str, extract_type: str = "text") -> list[str]:
    """Extract content matching a CSS selector.
    
    Args:
        html: Raw HTML string
        selector: CSS selector (e.g., "div.product-title", "h1", "a.nav-link")
        extract_type: What to extract - "text", "html", or an attribute name like "href"
    
    Returns:
        List of extracted values
    """
    soup = BeautifulSoup(html, "lxml")
    elements = soup.select(selector)
    results = []
    for el in elements:
        if extract_type == "text":
            results.append(el.get_text(strip=True))
        elif extract_type == "html":
            results.append(str(el))
        else:
            # Treat as attribute name
            val = el.get(extract_type)
            if val:
                results.append(val if isinstance(val, str) else " ".join(val))
    return results


def extract_by_xpath(html: str, xpath: str) -> list[str]:
    """Extract content matching an XPath expression.
    
    Args:
        html: Raw HTML string
        xpath: XPath expression (e.g., "//div[@class='price']/text()")
    
    Returns:
        List of extracted values (text content or attribute values)
    """
    try:
        tree = etree.HTML(html)
        if tree is None:
            return []
        results = tree.xpath(xpath)
        out = []
        for r in results:
            if isinstance(r, str):
                out.append(r.strip())
            elif hasattr(r, "text"):
                text = r.text or ""
                # Also get tail text and children text
                full_text = etree.tostring(r, method="text", encoding="unicode").strip()
                out.append(full_text if full_text else text.strip())
            else:
                out.append(str(r))
        return [x for x in out if x]
    except Exception as e:
        logger.warning(f"XPath extraction failed: {e}")
        return []


def extract_by_selectors(
    html: str,
    selectors: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    """Extract multiple named fields using CSS/XPath selectors.
    
    Args:
        html: Raw HTML string
        selectors: Dict mapping field names to selector configs, e.g.:
            {
                "title": {"css": "h1.product-title", "type": "text"},
                "price": {"css": "span.price", "type": "text"},
                "links": {"css": "a.nav", "type": "href"},
                "reviews": {"xpath": "//div[@itemprop='review']//p/text()"},
            }
    
    Returns:
        Dict mapping field names to extracted values
    """
    results = {}
    for field_name, config in selectors.items():
        if "css" in config:
            extract_type = config.get("type", "text")
            results[field_name] = extract_by_css(html, config["css"], extract_type)
        elif "xpath" in config:
            results[field_name] = extract_by_xpath(html, config["xpath"])
    return results
