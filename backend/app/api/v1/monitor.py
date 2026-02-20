"""URL change tracking / monitoring endpoints."""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.rate_limiter import check_rate_limit_full
from app.models.monitor import Monitor, MonitorCheck
from app.models.user import User
from app.schemas.monitor import (
    MonitorCreateRequest,
    MonitorUpdateRequest,
    MonitorResponse,
    MonitorListResponse,
    MonitorCheckResult,
    MonitorHistoryResponse,
)
from app.services.quota import check_quota, increment_usage

router = APIRouter()
logger = logging.getLogger(__name__)


def _monitor_to_response(m: Monitor) -> MonitorResponse:
    return MonitorResponse(
        id=str(m.id),
        name=m.name,
        url=m.url,
        check_interval_minutes=m.check_interval_minutes,
        css_selector=m.css_selector,
        notify_on=m.notify_on,
        keywords=m.keywords,
        is_active=m.is_active,
        threshold=m.threshold,
        webhook_url=m.webhook_url,
        last_check_at=m.last_check_at,
        last_change_at=m.last_change_at,
        last_status_code=m.last_status_code,
        total_checks=m.total_checks,
        total_changes=m.total_changes,
        created_at=m.created_at,
    )


@router.post("")
async def create_monitor(
    request: MonitorCreateRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new URL monitor for change tracking."""
    # Rate limit
    rl = await check_rate_limit_full(f"rate:monitor:{user.id}", 30)
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        from app.core.exceptions import RateLimitError

        raise RateLimitError("Monitor creation rate limit exceeded.")

    # Check quota
    await check_quota(db, user.id, "monitor")

    # Validate interval
    if request.check_interval_minutes < 5:
        raise BadRequestError("Minimum check interval is 5 minutes")
    if request.check_interval_minutes > 10080:  # 1 week
        raise BadRequestError("Maximum check interval is 10080 minutes (1 week)")

    # Validate notify_on
    valid_notify = {
        "any_change",
        "content_change",
        "status_change",
        "keyword_added",
        "keyword_removed",
    }
    if request.notify_on not in valid_notify:
        raise BadRequestError(f"notify_on must be one of: {', '.join(valid_notify)}")

    # Check monitor count limit
    result = await db.execute(
        select(func.count())
        .select_from(Monitor)
        .where(
            Monitor.user_id == user.id,
            Monitor.is_active == True,  # noqa: E712
        )
    )
    active_count = result.scalar() or 0
    if active_count >= 100:
        raise BadRequestError("Maximum 100 active monitors per account")

    now = datetime.now(timezone.utc)
    monitor = Monitor(
        user_id=user.id,
        name=request.name,
        url=request.url,
        check_interval_minutes=request.check_interval_minutes,
        css_selector=request.css_selector,
        notify_on=request.notify_on,
        keywords=request.keywords,
        webhook_url=request.webhook_url,
        webhook_secret=request.webhook_secret,
        headers=request.headers,
        cookies=request.cookies,
        only_main_content=request.only_main_content,
        threshold=request.threshold,
        next_check_at=now,  # Check immediately on creation
    )
    db.add(monitor)

    await increment_usage(db, user.id, "monitor")
    await db.flush()

    # Trigger initial check
    try:
        from app.workers.monitor_worker import check_single_monitor_task

        check_single_monitor_task.delay(str(monitor.id))
    except Exception as e:
        logger.warning(f"Failed to queue initial monitor check: {e}")

    await db.commit()

    return {
        "success": True,
        "monitor": _monitor_to_response(monitor),
    }


@router.get("")
async def list_monitors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(False),
):
    """List all monitors for the current user."""
    query = select(Monitor).where(Monitor.user_id == user.id)
    if active_only:
        query = query.where(Monitor.is_active == True)  # noqa: E712
    query = query.order_by(Monitor.created_at.desc())

    result = await db.execute(query)
    monitors = result.scalars().all()

    return MonitorListResponse(
        success=True,
        monitors=[_monitor_to_response(m) for m in monitors],
        total=len(monitors),
    )


@router.get("/{monitor_id}")
async def get_monitor(
    monitor_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific monitor."""
    monitor = await db.get(Monitor, UUID(monitor_id))
    if not monitor or monitor.user_id != user.id:
        raise NotFoundError("Monitor not found")

    return {
        "success": True,
        "monitor": _monitor_to_response(monitor),
    }


@router.patch("/{monitor_id}")
async def update_monitor(
    monitor_id: str,
    request: MonitorUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a monitor's configuration."""
    monitor = await db.get(Monitor, UUID(monitor_id))
    if not monitor or monitor.user_id != user.id:
        raise NotFoundError("Monitor not found")

    if request.name is not None:
        monitor.name = request.name
    if request.check_interval_minutes is not None:
        if request.check_interval_minutes < 5:
            raise BadRequestError("Minimum check interval is 5 minutes")
        monitor.check_interval_minutes = request.check_interval_minutes
        # Recalculate next check
        if monitor.last_check_at:
            monitor.next_check_at = monitor.last_check_at + timedelta(
                minutes=request.check_interval_minutes
            )
    if request.css_selector is not None:
        monitor.css_selector = request.css_selector
    if request.notify_on is not None:
        monitor.notify_on = request.notify_on
    if request.keywords is not None:
        monitor.keywords = request.keywords
    if request.webhook_url is not None:
        monitor.webhook_url = request.webhook_url
    if request.webhook_secret is not None:
        monitor.webhook_secret = request.webhook_secret
    if request.is_active is not None:
        monitor.is_active = request.is_active
        if request.is_active and not monitor.next_check_at:
            monitor.next_check_at = datetime.now(timezone.utc)
    if request.threshold is not None:
        monitor.threshold = request.threshold

    await db.commit()

    return {
        "success": True,
        "monitor": _monitor_to_response(monitor),
    }


@router.delete("/{monitor_id}")
async def delete_monitor(
    monitor_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a monitor and all its check history."""
    monitor = await db.get(Monitor, UUID(monitor_id))
    if not monitor or monitor.user_id != user.id:
        raise NotFoundError("Monitor not found")

    await db.delete(monitor)
    await db.commit()

    return {"success": True, "message": "Monitor deleted"}


@router.post("/{monitor_id}/check")
async def trigger_check(
    monitor_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate check for a monitor."""
    monitor = await db.get(Monitor, UUID(monitor_id))
    if not monitor or monitor.user_id != user.id:
        raise NotFoundError("Monitor not found")

    from app.workers.monitor_worker import check_single_monitor_task

    check_single_monitor_task.delay(str(monitor.id))

    return {"success": True, "message": "Check triggered"}


@router.get("/{monitor_id}/history")
async def get_monitor_history(
    monitor_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get check history for a monitor."""
    monitor = await db.get(Monitor, UUID(monitor_id))
    if not monitor or monitor.user_id != user.id:
        raise NotFoundError("Monitor not found")

    # Get total count
    count_result = await db.execute(
        select(func.count())
        .select_from(MonitorCheck)
        .where(MonitorCheck.monitor_id == monitor.id)
    )
    total = count_result.scalar() or 0

    # Get checks
    result = await db.execute(
        select(MonitorCheck)
        .where(MonitorCheck.monitor_id == monitor.id)
        .order_by(MonitorCheck.checked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    checks = result.scalars().all()

    return MonitorHistoryResponse(
        success=True,
        monitor_id=str(monitor.id),
        checks=[
            MonitorCheckResult(
                id=str(c.id),
                monitor_id=str(c.monitor_id),
                checked_at=c.checked_at,
                status_code=c.status_code,
                content_hash=c.content_hash,
                has_changed=c.has_changed,
                change_detail=c.change_detail,
                word_count=c.word_count,
                response_time_ms=c.response_time_ms,
            )
            for c in checks
        ],
        total=total,
    )
