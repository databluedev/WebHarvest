from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.scrape import ExtractConfig, PageMetadata


class SearchRequest(BaseModel):
    query: str
    num_results: int = 5  # Number of results to scrape
    engine: str = "google"  # google (SearXNG), duckduckgo, or brave
    google_api_key: str | None = None  # For Google Custom Search
    google_cx: str | None = None  # Google Custom Search Engine ID
    brave_api_key: str | None = None  # For Brave Search API
    formats: list[str] = [
        "markdown"
    ]  # All 7 formats: markdown, html, links, screenshot, structured_data, headings, images
    only_main_content: bool = False
    use_proxy: bool = False
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    mobile: bool = False
    mobile_device: str | None = None
    extract: ExtractConfig | None = None  # LLM extraction config applied to each result
    webhook_url: str | None = None
    webhook_secret: str | None = None


class SearchStartResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str = "started"
    message: str = "Search job started"


class SearchResultItem(BaseModel):
    model_config = {"exclude_none": True}

    id: str | None = None
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
    extract: dict[str, Any] | list[Any] | None = None
    metadata: PageMetadata | None = None
    error: str | None = None


class SearchStatusResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool
    job_id: UUID
    status: str
    query: str | None = None
    total_results: int = 0
    completed_results: int = 0
    data: list[SearchResultItem] | None = None
    error: str | None = None
