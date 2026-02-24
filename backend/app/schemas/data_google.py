"""Pydantic schemas for Google Data APIs (Scrapper Pool)."""

from pydantic import BaseModel, Field


# --- Request ---

class GoogleSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Search query")
    num_results: int = Field(10, ge=1, le=100, description="Number of results (max 100)")
    page: int = Field(1, ge=1, le=10, description="Result page (1-10)")
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(None, description="Country code for geo-targeting (gl parameter, e.g. us, uk, in)")
    safe_search: bool = Field(False, description="Enable safe search filter")
    time_range: str | None = Field(
        None,
        pattern=r"^(hour|day|week|month|year)$",
        description="Time filter: hour, day, week, month, year",
    )


# --- Response models ---

class Sitelink(BaseModel):
    title: str
    url: str


class GoogleOrganicResult(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank on the page")
    title: str
    url: str
    displayed_url: str | None = None
    snippet: str | None = None
    date: str | None = Field(None, description="Published date if shown")
    sitelinks: list[Sitelink] | None = None


class FeaturedSnippet(BaseModel):
    model_config = {"exclude_none": True}

    title: str
    url: str
    content: str
    type: str = Field("paragraph", description="paragraph, list, or table")


class PeopleAlsoAsk(BaseModel):
    question: str
    snippet: str | None = None


class RelatedSearch(BaseModel):
    query: str


class KnowledgePanel(BaseModel):
    model_config = {"exclude_none": True}

    title: str
    type: str | None = None
    description: str | None = None
    source: str | None = None
    image_url: str | None = None
    attributes: dict[str, str] | None = None


class GoogleSearchResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: str | None = Field(None, description="e.g. 'About 1,230,000 results'")
    time_taken: float = Field(..., description="API response time in seconds")
    organic_results: list[GoogleOrganicResult] = []
    featured_snippet: FeaturedSnippet | None = None
    people_also_ask: list[PeopleAlsoAsk] = []
    related_searches: list[RelatedSearch] = []
    knowledge_panel: KnowledgePanel | None = None


# ═══════════════════════════════════════════════════════════════════
# Google Shopping
# ═══════════════════════════════════════════════════════════════════


class GoogleShoppingRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Product search query")
    num_results: int = Field(10, ge=1, le=100, description="Number of products (max 100)")
    page: int = Field(1, ge=1, le=10, description="Starting page (1-10)")
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(None, description="Country code for geo-targeting (gl parameter)")

    # Filters
    sort_by: str | None = Field(
        None,
        pattern=r"^(relevance|price_low|price_high|rating|reviews)$",
        description="Sort order: relevance, price_low, price_high, rating, reviews",
    )
    min_price: float | None = Field(None, ge=0, description="Minimum price filter")
    max_price: float | None = Field(None, ge=0, description="Maximum price filter")
    condition: str | None = Field(
        None,
        pattern=r"^(new|used|any)$",
        description="Product condition: new, used, any",
    )
    min_rating: int | None = Field(
        None, ge=1, le=4, description="Minimum star rating (1-4)"
    )
    free_shipping: bool = Field(False, description="Only show free shipping products")


class GoogleShoppingProduct(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank")
    title: str
    url: str
    image_url: str | None = None
    price: str | None = Field(None, description="Displayed price string (e.g. '$29.99')")
    price_value: float | None = Field(None, description="Parsed numeric price")
    currency: str | None = Field(None, description="Currency code (USD, EUR, etc.)")
    original_price: str | None = Field(None, description="Original price if on sale")
    merchant: str | None = Field(None, description="Store/seller name")
    rating: float | None = Field(None, description="Star rating (0-5)")
    review_count: int | None = Field(None, description="Number of reviews")
    shipping: str | None = Field(None, description="Shipping info (e.g. 'Free shipping')")
    condition: str | None = Field(None, description="New, Used, Refurbished")
    badge: str | None = Field(None, description="Special badge (Best seller, Great price, etc.)")


class GoogleShoppingResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: str | None = None
    time_taken: float = Field(..., description="API response time in seconds")
    filters_applied: dict[str, str | float | bool] | None = Field(
        None, description="Echo of active filters"
    )
    products: list[GoogleShoppingProduct] = []
    related_searches: list[RelatedSearch] = []
