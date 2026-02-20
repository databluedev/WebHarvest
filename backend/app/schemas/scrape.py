from typing import Any

from pydantic import BaseModel


class ActionStep(BaseModel):
    type: str  # click, wait, scroll, type, screenshot, hover, press, select, fill_form, evaluate, go_back, go_forward
    selector: str | None = None
    milliseconds: int | None = None
    direction: str | None = None  # up, down
    amount: int | None = None
    text: str | None = None
    key: str | None = None  # For press action (Enter, Tab, Escape, etc.)
    value: str | None = None  # For select action (option value)
    script: str | None = None  # For evaluate action (JavaScript code)
    fields: dict[str, str] | None = None  # For fill_form action ({selector: value})
    button: str | None = None  # For click action: left, right, middle
    click_count: int | None = None  # For click action: double-click = 2
    modifiers: list[str] | None = None  # Alt, Control, Meta, Shift


class ExtractConfig(BaseModel):
    prompt: str | None = None
    schema_: dict[str, Any] | None = None  # JSON Schema

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "properties": {"schema": {"$ref": "#/properties/schema_"}}
        },
    }


class ScrapeRequest(BaseModel):
    url: str
    formats: list[str] = [
        "markdown"
    ]  # markdown, html, links, screenshot, structured_data, headings, images
    only_main_content: bool = True
    wait_for: int = 0  # ms to wait after page load
    timeout: int = 30000  # ms
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    actions: list[ActionStep] | None = None
    extract: ExtractConfig | None = None
    use_proxy: bool = False
    headers: dict[str, str] | None = None  # Custom HTTP headers to send
    cookies: dict[str, str] | None = None  # Custom cookies to send (name: value)
    mobile: bool = False  # Emulate mobile viewport
    mobile_device: str | None = (
        None  # Device preset name (e.g., "iphone_14", "pixel_7", "ipad_pro")
    )
    webhook_url: str | None = None  # Webhook URL for job completion notification
    webhook_secret: str | None = None  # HMAC secret for webhook signature


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
    error_code: str | None = (
        None  # BLOCKED_BY_WAF, CAPTCHA_REQUIRED, TIMEOUT, JS_REQUIRED, NETWORK_ERROR
    )
    job_id: str | None = None
