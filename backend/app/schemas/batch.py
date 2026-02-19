from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.scrape import PageMetadata


class BatchScrapeItem(BaseModel):
    url: str
    formats: list[str] | None = None  # Override per-URL, or use shared defaults
    only_main_content: bool | None = None
    wait_for: int | None = None
    timeout: int | None = None


class BatchScrapeRequest(BaseModel):
    urls: list[str] | None = None  # Simple list of URLs
    items: list[BatchScrapeItem] | None = None  # Per-URL overrides
    formats: list[str] = ["markdown"]  # Shared default formats
    only_main_content: bool = True
    wait_for: int = 0
    timeout: int = 30000
    concurrency: int = 5  # Max concurrent scrapes
    use_proxy: bool = False
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    mobile: bool = False
    webhook_url: str | None = None
    webhook_secret: str | None = None


class BatchStartResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str = "started"
    message: str = "Batch scrape job started"
    total_urls: int = 0


class BatchItemResult(BaseModel):
    url: str
    success: bool
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


class BatchStatusResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str
    total_urls: int
    completed_urls: int
    data: list[BatchItemResult] | None = None
    error: str | None = None
