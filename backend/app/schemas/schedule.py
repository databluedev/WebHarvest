from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ScheduleCreateRequest(BaseModel):
    name: str
    schedule_type: str  # scrape, crawl, batch
    config: dict[str, Any]
    cron_expression: str  # e.g., "0 */6 * * *"
    timezone: str = "UTC"
    webhook_url: str | None = None


class ScheduleUpdateRequest(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
    config: dict[str, Any] | None = None
    webhook_url: str | None = None


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    schedule_type: str
    config: dict[str, Any]
    cron_expression: str
    timezone: str
    is_active: bool
    last_run_at: str | None = None
    next_run_at: str | None = None
    next_run_human: str | None = None
    run_count: int
    webhook_url: str | None = None
    created_at: str
    updated_at: str


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]
    total: int
