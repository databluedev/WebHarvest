"""Usage tracking and analytics endpoints."""

import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, extract, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_usage_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate usage statistics for the current user."""
    # Total jobs
    total_jobs_q = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == user.id)
    )
    total_jobs = total_jobs_q.scalar() or 0

    # Jobs by type
    type_q = await db.execute(
        select(Job.type, func.count(Job.id))
        .where(Job.user_id == user.id)
        .group_by(Job.type)
    )
    jobs_by_type = dict(type_q.all())

    # Jobs by status
    status_q = await db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.user_id == user.id)
        .group_by(Job.status)
    )
    jobs_by_status = dict(status_q.all())

    # Total pages scraped
    pages_q = await db.execute(
        select(func.sum(Job.completed_pages)).where(Job.user_id == user.id)
    )
    total_pages = pages_q.scalar() or 0

    # Average pages per job
    avg_pages_q = await db.execute(
        select(func.avg(Job.completed_pages))
        .where(Job.user_id == user.id, Job.status == "completed")
    )
    avg_pages = round(float(avg_pages_q.scalar() or 0), 1)

    # Average duration (seconds) for completed jobs
    avg_duration = 0
    completed_with_times = await db.execute(
        select(Job.started_at, Job.completed_at)
        .where(
            Job.user_id == user.id,
            Job.status == "completed",
            Job.started_at.isnot(None),
            Job.completed_at.isnot(None),
        )
    )
    durations = []
    for started, completed in completed_with_times.all():
        if started and completed:
            durations.append((completed - started).total_seconds())
    if durations:
        avg_duration = round(sum(durations) / len(durations), 1)

    # Success rate
    completed_count = jobs_by_status.get("completed", 0)
    failed_count = jobs_by_status.get("failed", 0)
    success_rate = 0
    if completed_count + failed_count > 0:
        success_rate = round(completed_count / (completed_count + failed_count) * 100, 1)

    # Jobs per day (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_q = await db.execute(
        select(
            func.date_trunc('day', Job.created_at).label('day'),
            func.count(Job.id).label('count'),
        )
        .where(Job.user_id == user.id, Job.created_at >= thirty_days_ago)
        .group_by(text("day"))
        .order_by(text("day"))
    )
    jobs_per_day = [
        {"date": row.day.isoformat() if row.day else "", "count": row.count}
        for row in daily_q.all()
    ]

    return {
        "total_jobs": total_jobs,
        "total_pages_scraped": total_pages,
        "avg_pages_per_job": avg_pages,
        "avg_duration_seconds": avg_duration,
        "success_rate": success_rate,
        "jobs_by_type": jobs_by_type,
        "jobs_by_status": jobs_by_status,
        "jobs_per_day": jobs_per_day,
    }


@router.get("/history")
async def get_usage_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    type: str | None = Query(None, description="Filter by job type"),
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search in URL/query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|completed_at|status|type)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Paginated job history with filters."""
    query = select(Job).where(Job.user_id == user.id)

    if type:
        query = query.where(Job.type == type)
    if status:
        query = query.where(Job.status == status)
    if search:
        # Search in config JSONB for url or query fields
        query = query.where(
            or_(
                Job.config["url"].astext.ilike(f"%{search}%"),
                Job.config["query"].astext.ilike(f"%{search}%"),
            )
        )

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Sort
    sort_col = getattr(Job, sort_by, Job.created_at)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "jobs": [
            {
                "id": str(job.id),
                "type": job.type,
                "status": job.status,
                "config": job.config,
                "total_pages": job.total_pages,
                "completed_pages": job.completed_pages,
                "error": job.error,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "duration_seconds": (
                    round((job.completed_at - job.started_at).total_seconds(), 1)
                    if job.started_at and job.completed_at
                    else None
                ),
            }
            for job in jobs
        ],
    }


@router.get("/top-domains")
async def get_top_domains(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Top most scraped domains from job results."""
    # Get all URLs from job results for this user's jobs
    result = await db.execute(
        select(JobResult.url)
        .join(Job, JobResult.job_id == Job.id)
        .where(Job.user_id == user.id)
    )
    urls = [row[0] for row in result.all()]

    # Count domains
    domain_counts: dict[str, int] = {}
    for url in urls:
        try:
            domain = urlparse(url).netloc
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        except Exception:
            continue

    # Sort by count and return top N
    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    return {
        "domains": [
            {"domain": domain, "count": count}
            for domain, count in sorted_domains
        ],
        "total_unique_domains": len(domain_counts),
    }


@router.get("/quota")
async def get_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's monthly quota and usage."""
    from app.services.quota import get_quota_summary
    summary = await get_quota_summary(db, user.id)
    return {"success": True, **summary}


@router.get("/devices")
async def list_devices():
    """List all available mobile device presets for viewport emulation."""
    from app.services.mobile_presets import list_device_presets
    return {"success": True, "devices": list_device_presets()}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a job and its results."""
    from uuid import UUID
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Job not found")

    await db.delete(job)
    return {"success": True, "message": "Job deleted"}
