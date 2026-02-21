import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{job_id}/results/{result_id}",
    summary="Get job result detail",
    description="Retrieve the full content for a single page result within a job, "
    "including markdown, HTML, links, structured data, and metadata.",
)
async def get_job_result_detail(
    job_id: str,
    result_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full content for a single job result (on-demand loading)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Job not found")

    result = await db.execute(
        select(JobResult).where(
            JobResult.id == UUID(result_id),
            JobResult.job_id == job.id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundError("Result not found")

    # Build full response with all content
    structured_data = None
    headings = None
    images = None
    links_detail = None
    page_metadata = None

    if r.metadata_:
        meta = dict(r.metadata_)
        structured_data = meta.pop("structured_data", None)
        headings = meta.pop("headings", None)
        images = meta.pop("images", None)
        links_detail = meta.pop("links_detail", None)
        page_metadata = {k: v for k, v in meta.items() if k not in ("error",)}

    return {
        "id": str(r.id),
        "url": r.url,
        "markdown": r.markdown,
        "html": r.html,
        "links": r.links,
        "links_detail": links_detail,
        "screenshot": r.screenshot_url,
        "structured_data": structured_data,
        "headings": headings,
        "images": images,
        "extract": r.extract,
        "metadata": page_metadata,
    }


@router.post(
    "/{job_id}/retry",
    summary="Retry a failed job",
    description="Create a new job with the same configuration as a failed or cancelled job. "
    "The original job is preserved.",
)
async def retry_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed or cancelled job by creating a new job with the same config."""
    original_job = await db.get(Job, UUID(job_id))
    if not original_job or original_job.user_id != user.id:
        raise NotFoundError("Job not found")

    if original_job.status not in ("failed", "cancelled"):
        raise BadRequestError("Only failed or cancelled jobs can be retried")

    # Create a new job with the same config
    new_job = Job(
        id=uuid4(),
        user_id=user.id,
        type=original_job.type,
        status="pending",
        config=original_job.config,
        total_pages=original_job.total_pages or 0,
        completed_pages=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_job)
    await db.flush()

    # Dispatch to the correct Celery queue
    new_job_id = str(new_job.id)
    config = original_job.config or {}

    if original_job.type == "crawl":
        from app.workers.crawl_worker import process_crawl

        process_crawl.delay(new_job_id, config)
    elif original_job.type == "scrape":
        from app.workers.scrape_worker import process_scrape

        process_scrape.delay(new_job_id, config)
    elif original_job.type == "map":
        from app.workers.map_worker import process_map

        process_map.delay(new_job_id, config)
    elif original_job.type == "search":
        from app.workers.search_worker import process_search

        process_search.delay(new_job_id, config)
    else:
        raise BadRequestError(f"Cannot retry jobs of type '{original_job.type}'")

    return {
        "success": True,
        "message": "Job retried successfully",
        "original_job_id": job_id,
        "new_job_id": new_job_id,
        "type": original_job.type,
    }


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a job",
    description="Cancel a pending or running job. Completed or already-cancelled jobs "
    "cannot be cancelled.",
)
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or pending job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Job not found")

    if job.status not in ("pending", "running"):
        raise BadRequestError(f"Cannot cancel a job with status '{job.status}'")

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "success": True,
        "message": "Job cancelled",
        "job_id": job_id,
    }
