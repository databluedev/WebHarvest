from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.scrape import PageMetadata


class ScrapeOptions(BaseModel):
    formats: list[str] = ["markdown", "html", "links", "screenshot", "structured_data", "headings", "images"]
    only_main_content: bool = True
    wait_for: int = 0
    timeout: int = 30000
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    mobile: bool = False


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 100
    max_depth: int = 3
    concurrency: int = 3  # Concurrent scrapes (1-10)
    include_paths: list[str] | None = None  # glob patterns
    exclude_paths: list[str] | None = None
    allow_external_links: bool = False
    respect_robots_txt: bool = True
    scrape_options: ScrapeOptions | None = None
    use_proxy: bool = False
    webhook_url: str | None = None
    webhook_secret: str | None = None


class CrawlStartResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str = "started"
    message: str = "Crawl job started"


class CrawlPageData(BaseModel):
    url: str
    markdown: str | None = None
    html: str | None = None
    links: list[str] | None = None
    links_detail: dict | None = None
    screenshot: str | None = None
    structured_data: dict | None = None
    headings: list[dict] | None = None
    images: list[dict] | None = None
    metadata: PageMetadata | None = None


class CrawlStatusResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str  # pending, running, completed, failed, cancelled
    total_pages: int
    completed_pages: int
    data: list[CrawlPageData] | None = None
    error: str | None = None
