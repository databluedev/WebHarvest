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
