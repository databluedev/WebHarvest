import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{job_id}/results/{result_id}")
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
