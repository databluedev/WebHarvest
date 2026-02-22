"""Unit tests for product data extraction (JSON-LD, microdata, OpenGraph)."""

import pytest

from app.services.content import extract_product_data, extract_structured_data


# ---------------------------------------------------------------------------
# JSON-LD Product
# ---------------------------------------------------------------------------


class TestJsonLdProduct:
    """JSON-LD Product extraction (Amazon/Google-style)."""

    def test_basic_product_with_offer(self):
        """Standard JSON-LD Product with a single Offer."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Nike Air Max 90",
            "description": "Classic sneaker with visible Air unit",
            "sku": "CW7483-100",
            "brand": {"@type": "Brand", "name": "Nike"},
            "image": ["https://example.com/shoe1.jpg", "https://example.com/shoe2.jpg"],
            "offers": {
                "@type": "Offer",
                "price": "130.00",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock"
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": 4.5,
                "ratingCount": 1234
            }
        }
        </script>
        </head><body><h1>Nike Air Max 90</h1></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "Nike Air Max 90"
        assert product["brand"] == "Nike"
        assert product["price"] == "130.00"
        assert product["currency"] == "USD"
        assert product["availability"] == "InStock"
        assert product["sku"] == "CW7483-100"
        assert len(product["images"]) == 2
        assert product["rating"]["value"] == 4.5
        assert product["rating"]["count"] == 1234

    def test_aggregate_offer(self):
        """AggregateOffer with lowPrice/highPrice produces range."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Adjustable Widget",
            "offers": {
                "@type": "AggregateOffer",
                "lowPrice": "19.99",
                "highPrice": "49.99",
                "priceCurrency": "EUR",
                "availability": "https://schema.org/InStock"
            }
        }
        </script>
        </head><body></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["price"] == "19.99-49.99"
        assert product["currency"] == "EUR"

    def test_graph_product(self):
        """Product inside a JSON-LD @graph array."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebPage", "name": "Shop"},
                {
                    "@type": "Product",
                    "name": "Graphed Widget",
                    "offers": {"@type": "Offer", "price": "9.99", "priceCurrency": "GBP"}
                }
            ]
        }
        </script>
        </head><body></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "Graphed Widget"
        assert product["price"] == "9.99"

    def test_brand_as_string(self):
        """Brand can be a plain string instead of an object."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Simple Item", "brand": "Acme"}
        </script>
        </head><body></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["brand"] == "Acme"


# ---------------------------------------------------------------------------
# Microdata Product
# ---------------------------------------------------------------------------


class TestMicrodataProduct:
    """Microdata (itemscope/itemprop) product extraction (Shopify-style)."""

    def test_basic_microdata_product(self):
        """Parse a standard microdata Product block."""
        html = """
        <html><body>
        <div itemscope itemtype="https://schema.org/Product">
            <h1 itemprop="name">Shopify T-Shirt</h1>
            <meta itemprop="sku" content="TSHIRT-001" />
            <span itemprop="brand" itemscope itemtype="https://schema.org/Brand">
                <meta itemprop="name" content="CoolBrand" />
            </span>
            <img itemprop="image" src="https://example.com/tshirt.jpg" />
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                <meta itemprop="price" content="29.99" />
                <meta itemprop="priceCurrency" content="USD" />
                <link itemprop="availability" href="https://schema.org/InStock" />
            </div>
        </div>
        </body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "Shopify T-Shirt"
        assert product["sku"] == "TSHIRT-001"
        assert product["brand"] == "CoolBrand"
        assert product["price"] == "29.99"
        assert product["currency"] == "USD"
        assert product["availability"] == "InStock"
        assert "https://example.com/tshirt.jpg" in product["images"]


# ---------------------------------------------------------------------------
# OpenGraph Product
# ---------------------------------------------------------------------------


class TestOgProduct:
    """OpenGraph product tag extraction."""

    def test_og_only_product(self):
        """Product with only OG meta tags (no JSON-LD, no microdata)."""
        html = """
        <html><head>
        <meta property="og:type" content="product" />
        <meta property="og:title" content="OG Widget" />
        <meta property="og:description" content="A widget from OG land" />
        <meta property="og:image" content="https://example.com/widget.jpg" />
        <meta property="product:price:amount" content="15.50" />
        <meta property="product:price:currency" content="CAD" />
        <meta property="product:brand" content="OGBrand" />
        <meta property="product:availability" content="in stock" />
        </head><body><h1>OG Widget</h1></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "OG Widget"
        assert product["price"] == "15.50"
        assert product["currency"] == "CAD"
        assert product["brand"] == "OGBrand"
        assert product["availability"] == "in stock"


# ---------------------------------------------------------------------------
# Merged signals
# ---------------------------------------------------------------------------


class TestMergedProduct:
    """Tests that multiple sources are merged with correct priority."""

    def test_jsonld_takes_priority_over_microdata(self):
        """JSON-LD name wins over microdata name."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "JSON-LD Name", "sku": "JLD-001"}
        </script>
        </head><body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">Microdata Name</span>
            <meta itemprop="sku" content="MD-001" />
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                <meta itemprop="price" content="10.00" />
                <meta itemprop="priceCurrency" content="USD" />
            </div>
        </div>
        </body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "JSON-LD Name"
        assert product["sku"] == "JLD-001"
        # Price from microdata fills the gap
        assert product["price"] == "10.00"

    def test_microdata_fills_jsonld_gaps(self):
        """Microdata fills fields missing from JSON-LD."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Partial Product"}
        </script>
        </head><body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">Ignored Name</span>
            <span itemprop="brand" itemscope itemtype="https://schema.org/Brand">
                <meta itemprop="name" content="MicroBrand" />
            </span>
        </div>
        </body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["name"] == "Partial Product"
        assert product["brand"] == "MicroBrand"


# ---------------------------------------------------------------------------
# Non-product pages
# ---------------------------------------------------------------------------


class TestNonProductPage:
    """Verify non-product pages return None quickly."""

    def test_blog_post_returns_none(self):
        """A normal blog post has no product signals."""
        html = """
        <html><head>
        <meta property="og:type" content="article" />
        <meta property="og:title" content="How to code" />
        </head><body><h1>How to code</h1><p>Some text...</p></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)
        assert product is None

    def test_empty_html_returns_none(self):
        """Empty HTML returns None."""
        product = extract_product_data("<html><body></body></html>", {})
        assert product is None

    def test_no_structured_data_returns_none(self):
        """Plain page with no structured data at all."""
        product = extract_product_data("<html><body><p>Hello</p></body></html>", None)
        assert product is None


# ---------------------------------------------------------------------------
# Rating extraction
# ---------------------------------------------------------------------------


class TestRatingExtraction:
    """Tests for aggregateRating parsing."""

    def test_rating_with_review_count(self):
        """Rating with reviewCount instead of ratingCount."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Rated Widget",
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.2",
                "reviewCount": 567
            }
        }
        </script>
        </head><body></body></html>
        """
        sd = extract_structured_data(html)
        product = extract_product_data(html, sd)

        assert product is not None
        assert product["rating"]["value"] == 4.2
        assert product["rating"]["count"] == 567
