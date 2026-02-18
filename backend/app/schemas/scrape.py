from typing import Any

from pydantic import BaseModel, HttpUrl


class ActionStep(BaseModel):
    type: str  # click, wait, scroll, type, screenshot
    selector: str | None = None
    milliseconds: int | None = None
    direction: str | None = None  # up, down
    amount: int | None = None
    text: str | None = None


class ExtractConfig(BaseModel):
    prompt: str | None = None
    schema_: dict[str, Any] | None = None  # JSON Schema

    model_config = {"populate_by_name": True, "json_schema_extra": {"properties": {"schema": {"$ref": "#/properties/schema_"}}}}


class ScrapeRequest(BaseModel):
    url: str
    formats: list[str] = ["markdown"]  # markdown, html, links, screenshot, structured_data, headings, images
    only_main_content: bool = True
    wait_for: int = 0  # ms to wait after page load
    timeout: int = 30000  # ms
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    actions: list[ActionStep] | None = None
    extract: ExtractConfig | None = None
    use_proxy: bool = False


class PageMetadata(BaseModel):
    title: str | None = None
    description: str | None = None
    language: str | None = None
    source_url: str
    status_code: int
    word_count: int = 0
    reading_time_seconds: int = 0
    content_length: int = 0
    og_image: str | None = None
    canonical_url: str | None = None
    favicon: str | None = None
    robots: str | None = None
    response_headers: dict[str, str] | None = None


class ScrapeData(BaseModel):
    markdown: str | None = None
    html: str | None = None
    raw_html: str | None = None
    links: list[str] | None = None
    links_detail: dict | None = None  # internal/external breakdown with anchor text
    screenshot: str | None = None  # base64
    structured_data: dict | None = None  # JSON-LD, OpenGraph, Twitter Cards
    headings: list[dict] | None = None  # heading hierarchy
    images: list[dict] | None = None  # all images with metadata
    extract: dict[str, Any] | None = None
    metadata: PageMetadata


class ScrapeResponse(BaseModel):
    success: bool
    data: ScrapeData | None = None
    error: str | None = None
    job_id: str | None = None
