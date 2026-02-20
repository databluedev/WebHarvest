"""Schedule CRUD endpoints for recurring scrapes."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from croniter import croniter
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.job import Job
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
    ScheduleResponse,
    ScheduleListResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _compute_next_run(cron_expression: str, tz: str = "UTC") -> datetime:
    """Compute the next run time from a cron expression."""
    now = datetime.now(timezone.utc)
    cron = croniter(cron_expression, now)
    return cron.get_next(datetime).replace(tzinfo=timezone.utc)


def _human_readable_next(next_run: datetime | None) -> str | None:
    """Convert next_run to a human-readable relative time."""
    if not next_run:
        return None
    now = datetime.now(timezone.utc)
    # Handle naive datetimes (e.g. from SQLite which strips tz info)
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=timezone.utc)
    delta = next_run - now
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "overdue"
    if total_seconds < 60:
        return f"in {total_seconds}s"
    if total_seconds < 3600:
        return f"in {total_seconds // 60}m"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"in {hours}h"
    days = total_seconds // 86400
    return f"in {days}d"


def _schedule_to_response(schedule: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        schedule_type=schedule.schedule_type,
        config=schedule.config,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        next_run_human=_human_readable_next(schedule.next_run_at),
        run_count=schedule.run_count,
        webhook_url=schedule.webhook_url,
        created_at=schedule.created_at.isoformat() if schedule.created_at else "",
        updated_at=schedule.updated_at.isoformat() if schedule.updated_at else "",
    )


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scheduled scrape/crawl/batch."""
    # Validate cron expression
    if not croniter.is_valid(request.cron_expression):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Invalid cron expression")

    if request.schedule_type not in ("scrape", "crawl", "batch"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422, detail="schedule_type must be scrape, crawl, or batch"
        )

    next_run = _compute_next_run(request.cron_expression, request.timezone)

    schedule = Schedule(
        user_id=user.id,
        name=request.name,
        schedule_type=request.schedule_type,
        config=request.config,
        cron_expression=request.cron_expression,
        timezone=request.timezone,
        is_active=True,
        next_run_at=next_run,
        webhook_url=request.webhook_url,
    )
    db.add(schedule)
    await db.flush()

    return _schedule_to_response(schedule)


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all schedules for the current user."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.user_id == user.id)
        .order_by(Schedule.created_at.desc())
    )
    schedules = result.scalars().all()

    count_q = await db.execute(
        select(func.count(Schedule.id)).where(Schedule.user_id == user.id)
    )
    total = count_q.scalar() or 0

    return ScheduleListResponse(
        schedules=[_schedule_to_response(s) for s in schedules],
        total=total,
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a schedule with its recent run history."""
    schedule = await db.get(Schedule, UUID(schedule_id))
    if not schedule or schedule.user_id != user.id:
        raise NotFoundError("Schedule not found")

    resp = _schedule_to_response(schedule)
    return resp


@router.get("/{schedule_id}/runs")
async def get_schedule_runs(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent jobs triggered by this schedule."""
    schedule = await db.get(Schedule, UUID(schedule_id))
    if not schedule or schedule.user_id != user.id:
        raise NotFoundError("Schedule not found")

    # Get jobs created by this schedule (stored in config.schedule_id)
    result = await db.execute(
        select(Job)
        .where(
            Job.user_id == user.id,
            Job.config["schedule_id"].astext == schedule_id,
        )
        .order_by(Job.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()

    return {
        "runs": [
            {
                "id": str(job.id),
                "type": job.type,
                "status": job.status,
                "total_pages": job.total_pages,
                "completed_pages": job.completed_pages,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "error": job.error,
            }
            for job in jobs
        ]
    }


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a schedule."""
    schedule = await db.get(Schedule, UUID(schedule_id))
    if not schedule or schedule.user_id != user.id:
        raise NotFoundError("Schedule not found")

    if request.name is not None:
        schedule.name = request.name
    if request.cron_expression is not None:
        if not croniter.is_valid(request.cron_expression):
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="Invalid cron expression")
        schedule.cron_expression = request.cron_expression
        schedule.next_run_at = _compute_next_run(
            request.cron_expression, request.timezone or schedule.timezone
        )
    if request.timezone is not None:
        schedule.timezone = request.timezone
    if request.is_active is not None:
        schedule.is_active = request.is_active
        if request.is_active and schedule.next_run_at is None:
            schedule.next_run_at = _compute_next_run(
                schedule.cron_expression, schedule.timezone
            )
    if request.config is not None:
        schedule.config = request.config
    if request.webhook_url is not None:
        schedule.webhook_url = request.webhook_url

    schedule.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return _schedule_to_response(schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a schedule."""
    schedule = await db.get(Schedule, UUID(schedule_id))
    if not schedule or schedule.user_id != user.id:
        raise NotFoundError("Schedule not found")

    await db.delete(schedule)
    return {"success": True, "message": "Schedule deleted"}


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a schedule now."""
    schedule = await db.get(Schedule, UUID(schedule_id))
    if not schedule or schedule.user_id != user.id:
        raise NotFoundError("Schedule not found")

    # Create a job from the schedule config
    config = dict(schedule.config)
    config["schedule_id"] = schedule_id

    job = Job(
        user_id=user.id,
        type=schedule.schedule_type,
        status="pending",
        config=config,
    )
    db.add(job)
    await db.flush()

    # Dispatch to the appropriate worker
    if schedule.schedule_type == "crawl":
        from app.workers.crawl_worker import process_crawl

        process_crawl.delay(str(job.id), config)
    elif schedule.schedule_type == "batch":
        from app.workers.batch_worker import process_batch

        process_batch.delay(str(job.id), config)
    elif schedule.schedule_type == "scrape":
        from app.workers.scrape_worker import process_scrape

        process_scrape.delay(str(job.id), config)

    # Update schedule
    schedule.last_run_at = datetime.now(timezone.utc)
    schedule.run_count += 1
    schedule.next_run_at = _compute_next_run(
        schedule.cron_expression, schedule.timezone
    )

    return {
        "success": True,
        "job_id": str(job.id),
        "message": f"Schedule triggered, job {job.id} created",
    }
