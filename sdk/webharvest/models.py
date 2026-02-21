"""Pydantic models for WebHarvest API request and response types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / nested models
# ---------------------------------------------------------------------------


class PageMetadata(BaseModel):
    """Metadata extracted from a scraped page."""

    title: str | None = None
    description: str | None = None
    language: str | None = None
    source_url: str | None = None
    status_code: int | None = None
    word_count: int = 0
    reading_time_seconds: int = 0
    content_length: int = 0
    og_image: str | None = None
    canonical_url: str | None = None
    favicon: str | None = None
    robots: str | None = None
    response_headers: dict[str, str] | None = None


class PageData(BaseModel):
    """Content and metadata for a single scraped page."""

    url: str | None = None
    markdown: str | None = None
    html: str | None = None
    raw_html: str | None = None
    links: list[str] | None = None
    links_detail: dict | None = None
    screenshot: str | None = None
    structured_data: dict | None = None
    headings: list[dict] | None = None
    images: list[dict] | None = None
    extract: dict[str, Any] | None = None
    metadata: PageMetadata | None = None


class CrawlPageData(BaseModel):
    """Content and metadata for a single page within a crawl job."""

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


class SearchResultItem(BaseModel):
    """Result for a single search result page."""

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


class LinkResult(BaseModel):
    """A single link discovered by the map endpoint."""

    url: str
    title: str | None = None
    description: str | None = None
    lastmod: str | None = None
    priority: float | None = None


class DayCount(BaseModel):
    """Jobs executed on a particular day."""

    date: str
    count: int


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------


class ScrapeResult(BaseModel):
    """Response from the /v1/scrape endpoint."""

    success: bool
    data: PageData | None = None
    error: str | None = None


class CrawlJob(BaseModel):
    """Response from starting a new crawl via POST /v1/crawl."""

    success: bool
    job_id: str
    status: str = "started"
    message: str | None = None


class CrawlStatus(BaseModel):
    """Response from GET /v1/crawl/{job_id}."""

    success: bool
    job_id: str
    status: str
    total_pages: int = 0
    completed_pages: int = 0
    data: list[CrawlPageData] | None = None
    error: str | None = None


class SearchJob(BaseModel):
    """Response from starting a new search via POST /v1/search."""

    success: bool
    job_id: str
    status: str = "started"
    message: str | None = None


class SearchStatus(BaseModel):
    """Response from GET /v1/search/{job_id}."""

    success: bool
    job_id: str
    status: str
    query: str | None = None
    total_results: int = 0
    completed_results: int = 0
    data: list[SearchResultItem] | None = None
    error: str | None = None


class MapResult(BaseModel):
    """Response from POST /v1/map."""

    success: bool
    total: int = 0
    links: list[LinkResult] = Field(default_factory=list)
    error: str | None = None


class UsageStats(BaseModel):
    """Aggregate usage statistics from GET /v1/usage/stats."""

    total_jobs: int = 0
    total_pages_scraped: int = 0
    avg_pages_per_job: float = 0.0
    avg_duration_seconds: float = 0.0
    success_rate: float = 0.0
    jobs_by_type: dict[str, int] = Field(default_factory=dict)
    jobs_by_status: dict[str, int] = Field(default_factory=dict)
    jobs_per_day: list[DayCount] = Field(default_factory=list)


class JobHistoryItem(BaseModel):
    """A single job entry in the usage history."""

    id: str
    type: str
    status: str
    config: Any | None = None
    total_pages: int = 0
    completed_pages: int = 0
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    duration_seconds: float | None = None


class UsageHistory(BaseModel):
    """Paginated usage history from GET /v1/usage/history."""

    total: int = 0
    page: int = 1
    per_page: int = 20
    total_pages: int = 0
    jobs: list[JobHistoryItem] = Field(default_factory=list)


class TopDomains(BaseModel):
    """Response from GET /v1/usage/top-domains."""

    domains: list[dict[str, Any]] = Field(default_factory=list)
    total_unique_domains: int = 0


class Schedule(BaseModel):
    """A single schedule entry."""

    id: str
    name: str
    schedule_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    cron_expression: str
    timezone: str = "UTC"
    is_active: bool = True
    last_run_at: str | None = None
    next_run_at: str | None = None
    next_run_human: str | None = None
    run_count: int = 0
    webhook_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ScheduleList(BaseModel):
    """Response from GET /v1/schedules."""

    schedules: list[Schedule] = Field(default_factory=list)
    total: int = 0


class ScheduleRuns(BaseModel):
    """Response from GET /v1/schedules/{id}/runs."""

    runs: list[dict[str, Any]] = Field(default_factory=list)


class ScheduleTrigger(BaseModel):
    """Response from POST /v1/schedules/{id}/trigger."""

    success: bool
    job_id: str | None = None
    message: str | None = None


class TokenResponse(BaseModel):
    """Response from login/register containing the access token."""

    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """Current user profile from GET /v1/auth/me."""

    id: str
    email: str
    name: str | None = None
    created_at: str | None = None
