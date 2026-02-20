"""Webhook management and debug endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.webhook_delivery import WebhookDelivery
from app.models.user import User
from app.services.webhook import send_webhook_test

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/deliveries",
    summary="List webhook deliveries",
    description="List webhook delivery logs with optional filtering by event type, "
    "success status, or job ID. Results are paginated.",
)
async def list_deliveries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event: str | None = Query(None),
    success: bool | None = Query(None),
    job_id: str | None = Query(None),
):
    """List webhook delivery logs for the current user."""
    query = select(WebhookDelivery).where(WebhookDelivery.user_id == user.id)

    if event:
        query = query.where(WebhookDelivery.event == event)
    if success is not None:
        query = query.where(WebhookDelivery.success == success)
    if job_id:
        query = query.where(WebhookDelivery.job_id == UUID(job_id))

    # Get total count
    count_query = (
        select(func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.user_id == user.id)
    )
    if event:
        count_query = count_query.where(WebhookDelivery.event == event)
    if success is not None:
        count_query = count_query.where(WebhookDelivery.success == success)
    if job_id:
        count_query = count_query.where(WebhookDelivery.job_id == UUID(job_id))

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(
        query.order_by(WebhookDelivery.created_at.desc()).offset(offset).limit(limit)
    )
    deliveries = result.scalars().all()

    return {
        "success": True,
        "deliveries": [
            {
                "id": str(d.id),
                "job_id": str(d.job_id) if d.job_id else None,
                "url": d.url,
                "event": d.event,
                "payload": d.payload,
                "status_code": d.status_code,
                "response_body": d.response_body,
                "response_time_ms": d.response_time_ms,
                "success": d.success,
                "attempt": d.attempt,
                "max_attempts": d.max_attempts,
                "error": d.error,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deliveries
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/deliveries/{delivery_id}",
    summary="Get webhook delivery details",
    description="Returns full details for a specific webhook delivery including "
    "request/response headers and body.",
)
async def get_delivery(
    delivery_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a specific webhook delivery."""
    delivery = await db.get(WebhookDelivery, UUID(delivery_id))
    if not delivery or delivery.user_id != user.id:
        raise NotFoundError("Webhook delivery not found")

    return {
        "success": True,
        "delivery": {
            "id": str(delivery.id),
            "job_id": str(delivery.job_id) if delivery.job_id else None,
            "url": delivery.url,
            "event": delivery.event,
            "payload": delivery.payload,
            "request_headers": delivery.request_headers,
            "status_code": delivery.status_code,
            "response_body": delivery.response_body,
            "response_headers": delivery.response_headers,
            "response_time_ms": delivery.response_time_ms,
            "success": delivery.success,
            "attempt": delivery.attempt,
            "max_attempts": delivery.max_attempts,
            "error": delivery.error,
            "next_retry_at": delivery.next_retry_at.isoformat()
            if delivery.next_retry_at
            else None,
            "created_at": delivery.created_at.isoformat()
            if delivery.created_at
            else None,
        },
    }


@router.post(
    "/test",
    summary="Send test webhook",
    description="Send a test payload to a webhook URL to verify connectivity and "
    "HMAC signature validation.",
)
async def test_webhook(
    url: str,
    secret: str | None = None,
    user: User = Depends(get_current_user),
):
    """Send a test webhook to verify endpoint connectivity."""
    result = await send_webhook_test(url, secret)
    return {
        "success": result["success"],
        "test_result": result,
    }


@router.get(
    "/stats",
    summary="Get webhook statistics",
    description="Returns delivery statistics including total count, success rate, "
    "average response time, and breakdown by event type.",
)
async def webhook_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get webhook delivery statistics for the current user."""
    # Total deliveries
    total_result = await db.execute(
        select(func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.user_id == user.id)
    )
    total = total_result.scalar() or 0

    # Success count
    success_result = await db.execute(
        select(func.count())
        .select_from(WebhookDelivery)
        .where(
            WebhookDelivery.user_id == user.id,
            WebhookDelivery.success == True,  # noqa: E712
        )
    )
    success_count = success_result.scalar() or 0

    # Failed count
    failed_count = total - success_count

    # Avg response time
    avg_result = await db.execute(
        select(func.avg(WebhookDelivery.response_time_ms)).where(
            WebhookDelivery.user_id == user.id,
            WebhookDelivery.success == True,  # noqa: E712
        )
    )
    avg_response_time = avg_result.scalar()

    # Events breakdown
    events_result = await db.execute(
        select(
            WebhookDelivery.event,
            func.count().label("count"),
        )
        .where(WebhookDelivery.user_id == user.id)
        .group_by(WebhookDelivery.event)
    )
    events = {row[0]: row[1] for row in events_result.all()}

    return {
        "success": True,
        "stats": {
            "total_deliveries": total,
            "successful": success_count,
            "failed": failed_count,
            "success_rate": round(success_count / total * 100, 1) if total else 0,
            "avg_response_time_ms": round(avg_response_time)
            if avg_response_time
            else 0,
            "events_breakdown": events,
        },
    }
