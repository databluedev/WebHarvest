"""Pydantic schemas for Amazon Data APIs."""

from pydantic import BaseModel, Field


# --- Request ---


class AmazonProductsRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Product search query")
    num_results: int = Field(
        0, ge=0, le=960,
        description="Max products to fetch. 0 = fetch all pages until exhausted (max ~960).",
    )
    page: int = Field(1, ge=1, le=20, description="Starting page (1-20)")
    domain: str = Field(
        "amazon.in",
        description="Amazon domain (e.g. amazon.in, amazon.com, amazon.co.uk, amazon.de)",
    )
    sort_by: str | None = Field(
        None,
        pattern=r"^(relevance|price_low|price_high|rating|newest)$",
        description="Sort order: relevance, price_low, price_high, rating, newest",
    )
    min_price: int | None = Field(None, ge=0, description="Minimum price filter (in whole currency units)")
    max_price: int | None = Field(None, ge=0, description="Maximum price filter (in whole currency units)")
    prime_only: bool = Field(False, description="Filter to Prime-eligible products only")
    language: str = Field("en", description="Language code (hl parameter)")


# --- Response models ---


class AmazonProduct(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank in results")
    asin: str = Field(..., description="Amazon Standard Identification Number")
    title: str
    url: str = Field(..., description="Product page URL")
    image_url: str | None = Field(None, description="Product image URL")
    price: str | None = Field(None, description="Displayed price string (e.g. '₹1,299')")
    price_value: float | None = Field(None, description="Parsed numeric price")
    currency: str | None = Field(None, description="Currency symbol (e.g. '₹', '$', '£')")
    original_price: str | None = Field(None, description="Original price if on sale")
    discount: str | None = Field(None, description="Discount text (e.g. '30% off')")
    rating: float | None = Field(None, description="Star rating (0-5)")
    review_count: int | None = Field(None, description="Number of reviews")
    is_prime: bool = Field(False, description="Prime-eligible product")
    is_sponsored: bool = Field(False, description="Sponsored/ad listing")
    badge: str | None = Field(None, description="Special badge (Best Seller, Amazon's Choice, etc.)")
    delivery: str | None = Field(None, description="Delivery info text")
    seller: str | None = Field(None, description="Seller/brand name")
    coupon: str | None = Field(None, description="Coupon text (e.g. 'Save 5% with coupon')")


class AmazonProductsResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    domain: str = Field(..., description="Amazon domain used")
    total_results: str | None = Field(None, description="Total results text from Amazon")
    pages_fetched: int = Field(0, description="Number of pages fetched")
    time_taken: float = Field(..., description="API response time in seconds")
    products: list[AmazonProduct] = []
    search_url: str | None = Field(None, description="Amazon search URL used")
    error: str | None = Field(None, description="Error message if the search failed")
