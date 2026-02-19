"""Schemas for standalone /extract endpoint."""

from typing import Any

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    """Extract structured data from content using LLM.

    Accepts either raw content (markdown/HTML) or a URL to scrape first.
    At least one of `content`, `html`, or `url` must be provided.
    """

    # Content sources — provide at least one
    content: str | None = None  # Raw markdown/text content
    html: str | None = None  # Raw HTML to convert + extract from
    url: str | None = None  # URL to scrape first, then extract
    urls: list[str] | None = None  # Multiple URLs to scrape + extract

    # Extraction config
    prompt: str | None = None  # Natural language extraction instruction
    schema_: dict[str, Any] | None = None  # JSON Schema for structured output

    # LLM provider config
    provider: str | None = None  # openai, anthropic, groq, etc.

    # Scrape options (only used when url/urls provided)
    only_main_content: bool = True
    wait_for: int = 0
    timeout: int = 30000
    use_proxy: bool = False
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None

    # Webhook
    webhook_url: str | None = None
    webhook_secret: str | None = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "properties": {"schema": {"$ref": "#/properties/schema_"}}
        },
    }


class ExtractResult(BaseModel):
    """Single extraction result."""

    url: str | None = None
    extract: dict[str, Any] | list[Any] | None = None
    content_length: int = 0
    error: str | None = None


class ExtractResponse(BaseModel):
    """Response for /extract endpoint."""

    success: bool
    data: ExtractResult | list[ExtractResult] | None = None
    error: str | None = None
    job_id: str | None = None


class ExtractStartResponse(BaseModel):
    """Response for async /extract endpoint (multi-URL)."""

    success: bool
    job_id: str
    status: str = "started"
    message: str = "Extraction job started"
    total_urls: int = 0


class ExtractStatusResponse(BaseModel):
    """Status response for async extraction jobs."""

    success: bool
    job_id: str
    status: str
    total_urls: int = 0
    completed_urls: int = 0
    data: list[ExtractResult] | None = None
    error: str | None = None
