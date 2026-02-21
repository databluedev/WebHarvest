"""Credit/quota enforcement service.

Tracks per-user monthly usage and enforces limits.
Limits of -1 mean unlimited usage.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RateLimitError
from app.models.usage_quota import UsageQuota

logger = logging.getLogger(__name__)

# Default limits for new users (generous free tier)
DEFAULT_LIMITS = {
    "scrape_limit": 10000,
    "crawl_limit": 1000,
    "extract_limit": 5000,
    "search_limit": 2000,
    "map_limit": 5000,
    "monitor_limit": 100,
}


def _current_period() -> str:
    """Return current period string in YYYY-MM format."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_or_create_quota(db: AsyncSession, user_id: UUID) -> UsageQuota:
    """Get or create the current month's quota record for a user."""
    period = _current_period()
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user_id,
            UsageQuota.period == period,
        )
    )
    quota = result.scalar_one_or_none()

    if not quota:
        # Check if user has a previous month's quota to inherit limits from
        prev_result = await db.execute(
            select(UsageQuota)
            .where(UsageQuota.user_id == user_id)
            .order_by(UsageQuota.created_at.desc())
            .limit(1)
        )
        prev_quota = prev_result.scalar_one_or_none()

        limits = {}
        if prev_quota:
            # Inherit limits from previous period
            for key in DEFAULT_LIMITS:
                limits[key] = getattr(prev_quota, key)
        else:
            limits = DEFAULT_LIMITS.copy()

        quota = UsageQuota(
            user_id=user_id,
            period=period,
            **limits,
        )
        db.add(quota)
        await db.flush()

    return quota


async def check_quota(db: AsyncSession, user_id: UUID, operation: str) -> UsageQuota:
    """Check if user has remaining quota for an operation.

    Args:
        db: Database session
        user_id: User UUID
        operation: One of: scrape, crawl, extract, search, map, monitor

    Returns:
        The UsageQuota record

    Raises:
        RateLimitError if quota exceeded
    """
    quota = await get_or_create_quota(db, user_id)

    limit_field = f"{operation}_limit"
    used_field = f"{operation}_used"

    limit_val = getattr(quota, limit_field, -1)
    used_val = getattr(quota, used_field, 0)

    # -1 means unlimited
    if limit_val != -1 and used_val >= limit_val:
        raise RateLimitError(
            detail=f"Monthly {operation} quota exceeded ({used_val}/{limit_val}). "
            f"Upgrade your plan or wait until next month.",
            headers={
                "X-Quota-Limit": str(limit_val),
                "X-Quota-Used": str(used_val),
                "X-Quota-Remaining": "0",
                "Retry-After": "86400",
            },
        )

    return quota


async def increment_usage(
    db: AsyncSession,
    user_id: UUID,
    operation: str,
    count: int = 1,
    pages: int = 0,
    bytes_processed: int = 0,
):
    """Increment usage counter for an operation.

    Args:
        db: Database session
        user_id: User UUID
        operation: One of: scrape, crawl, extract, search, map, monitor
        count: Number of operations to add
        pages: Number of pages scraped
        bytes_processed: Bytes of content processed
    """
    quota = await get_or_create_quota(db, user_id)
    used_field = f"{operation}_used"

    current = getattr(quota, used_field, 0)
    setattr(quota, used_field, current + count)

    if pages:
        quota.total_pages_scraped += pages
    if bytes_processed:
        quota.total_bytes_processed += bytes_processed

    await db.flush()


async def get_quota_summary(db: AsyncSession, user_id: UUID) -> dict:
    """Get a summary of the user's current quota usage."""
    quota = await get_or_create_quota(db, user_id)

    operations = ["scrape", "crawl", "extract", "search", "map", "monitor"]
    summary = {
        "period": quota.period,
        "total_pages_scraped": quota.total_pages_scraped,
        "total_bytes_processed": quota.total_bytes_processed,
        "operations": {},
    }

    for op in operations:
        limit_val = getattr(quota, f"{op}_limit")
        used_val = getattr(quota, f"{op}_used")
        summary["operations"][op] = {
            "limit": limit_val,
            "used": used_val,
            "remaining": max(0, limit_val - used_val) if limit_val != -1 else -1,
            "unlimited": limit_val == -1,
        }

    return summary
