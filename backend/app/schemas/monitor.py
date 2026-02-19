"""Schemas for URL change tracking / monitoring."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MonitorCreateRequest(BaseModel):
    """Create a new URL monitor."""

    name: str
    url: str
    check_interval_minutes: int = 60  # Default: hourly
    css_selector: str | None = None  # Monitor specific element
    notify_on: str = "any_change"  # any_change, content_change, status_change, keyword_added, keyword_removed
    keywords: list[str] | None = None  # Keywords to watch for
    webhook_url: str | None = None
    webhook_secret: str | None = None
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    only_main_content: bool = True
    threshold: float = 0.05  # Minimum change ratio to trigger (0.0-1.0)


class MonitorUpdateRequest(BaseModel):
    """Update an existing monitor."""

    name: str | None = None
    check_interval_minutes: int | None = None
    css_selector: str | None = None
    notify_on: str | None = None
    keywords: list[str] | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None
    is_active: bool | None = None
    threshold: float | None = None


class MonitorChangeDetail(BaseModel):
    """Details of a detected change."""

    change_type: str  # content_changed, status_changed, keyword_found, keyword_lost, element_changed
    summary: str
    diff_stats: dict[str, Any] | None = None  # {added_lines, removed_lines, similarity_ratio}
    old_content_preview: str | None = None
    new_content_preview: str | None = None
    old_status_code: int | None = None
    new_status_code: int | None = None
    keywords_found: list[str] | None = None
    keywords_lost: list[str] | None = None


class MonitorCheckResult(BaseModel):
    """Result of a single monitor check."""

    id: str
    monitor_id: str
    checked_at: datetime
    status_code: int
    content_hash: str
    has_changed: bool
    change_detail: MonitorChangeDetail | None = None
    word_count: int = 0
    response_time_ms: int = 0


class MonitorResponse(BaseModel):
    """Full monitor info."""

    id: str
    name: str
    url: str
    check_interval_minutes: int
    css_selector: str | None = None
    notify_on: str
    keywords: list[str] | None = None
    is_active: bool
    threshold: float
    webhook_url: str | None = None
    last_check_at: datetime | None = None
    last_change_at: datetime | None = None
    last_status_code: int | None = None
    total_checks: int = 0
    total_changes: int = 0
    created_at: datetime


class MonitorListResponse(BaseModel):
    """List of monitors."""

    success: bool
    monitors: list[MonitorResponse]
    total: int


class MonitorHistoryResponse(BaseModel):
    """Check history for a monitor."""

    success: bool
    monitor_id: str
    checks: list[MonitorCheckResult]
    total: int
