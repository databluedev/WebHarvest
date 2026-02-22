from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.scrape import PageMetadata, ExtractConfig, _normalize_url


class ScrapeOptions(BaseModel):
    formats: list[str] = [
        "markdown",
    ]
    only_main_content: bool = False
    wait_for: int = 0
    timeout: int = 30000
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    mobile: bool = False
    mobile_device: str | None = None
    extract: ExtractConfig | None = None  # LLM extraction config for each page


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 100
    max_depth: int = 3
    concurrency: int = 3  # Concurrent scrapes (1-10)
    include_paths: list[str] | None = None  # glob patterns
    exclude_paths: list[str] | None = None
    allow_external_links: bool = False
    respect_robots_txt: bool = True
    crawl_strategy: str = "bfs"  # "bfs", "dfs", or "bff" (best-first)
    scrape_options: ScrapeOptions | None = None
    use_proxy: bool = False
    filter_faceted_urls: bool = True  # Deduplicate faceted/navigation URL variations
    webhook_url: str | None = None
    webhook_secret: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _add_protocol(cls, v: str) -> str:
        return _normalize_url(v)


class CrawlStartResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str = "started"
    message: str = "Crawl job started"


class CrawlPageData(BaseModel):
    model_config = {"exclude_none": True}

    id: str | None = None
    url: str
    markdown: str | None = None
    html: str | None = None
    links: list[str] | None = None
    links_detail: dict | None = None
    screenshot: str | None = None
    structured_data: dict | None = None
    headings: list[dict] | None = None
    images: list[dict] | None = None
    product_data: dict | None = None
    tables: list[dict] | None = None
    selector_data: dict | None = None
    extract: dict[str, Any] | list[Any] | None = None
    metadata: PageMetadata | None = None


class CrawlStatusResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool
    job_id: UUID
    status: str  # pending, running, completed, failed, cancelled
    total_pages: int
    completed_pages: int
    data: list[CrawlPageData] | None = None
    total_results: int = 0
    page: int = 1
    per_page: int = 20
    error: str | None = None
