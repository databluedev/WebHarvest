from uuid import UUID

from pydantic import BaseModel

from app.schemas.scrape import PageMetadata


class SearchRequest(BaseModel):
    query: str
    num_results: int = 5  # Number of results to scrape
    engine: str = "duckduckgo"  # duckduckgo, google, or brave
    google_api_key: str | None = None  # For Google Custom Search
    google_cx: str | None = None  # Google Custom Search Engine ID
    brave_api_key: str | None = None  # For Brave Search API
    formats: list[str] = ["markdown"]
    use_proxy: bool = False
    webhook_url: str | None = None
    webhook_secret: str | None = None


class SearchStartResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str = "started"
    message: str = "Search job started"


class SearchResultItem(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    success: bool = True
    markdown: str | None = None
    html: str | None = None
    links: list[str] | None = None
    links_detail: dict | None = None
    screenshot: str | None = None
    structured_data: dict | None = None
    headings: list[dict] | None = None
    images: list[dict] | None = None
    metadata: PageMetadata | None = None
    error: str | None = None


class SearchStatusResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str
    query: str | None = None
    total_results: int = 0
    completed_results: int = 0
    data: list[SearchResultItem] | None = None
    error: str | None = None
