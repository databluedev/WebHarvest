import csv
import io
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.core.job_cache import get_cached_response, set_cached_response
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.map import MapRequest, MapResponse, LinkResult
from app.core.cache import get_cached_map
from app.workers.map_worker import process_map

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=MapResponse,
    summary="Map website URLs",
    description="Discover and map all URLs on a website by crawling sitemaps and link structures. Returns a list of discovered URLs with their titles, descriptions, and metadata. Rate-limited per user.",
)
async def map_site(
    request: MapRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Map all URLs on a website. Returns discovered URLs with titles and descriptions."""
    # Rate limiting
    rl = await check_rate_limit_full(f"rate:map:{user.id}", settings.RATE_LIMIT_MAP)
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Map rate limit exceeded. Try again in a minute.")

    # Cross-user cache check — return instantly if another user already mapped this
    cached = await get_cached_map(
        request.url, request.limit, request.include_subdomains,
        request.use_sitemap, request.search,
    )
    if cached:
        links = [LinkResult(**l) if isinstance(l, dict) else l for l in cached]
        return MapResponse(success=True, total=len(links), links=links)

    # Create job record
    job = Job(
        user_id=user.id,
        type="map",
        status="pending",
        config=request.model_dump(),
        total_pages=0,
    )
    db.add(job)
    await db.flush()

    # Dispatch to Celery worker (non-blocking)
    process_map.delay(str(job.id), request.model_dump())

    return MapResponse(
        success=True,
        total=0,
        links=[],
        job_id=str(job.id),
    )


@router.get(
    "/{job_id}",
    summary="Get map job status",
    description="Retrieve the current status and discovered URLs of a map job. Completed and failed jobs are served from cache for faster response times.",
)
async def get_map_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and results of a map job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "map":
        raise NotFoundError("Map job not found")

    # Return cached response instantly for completed/failed jobs
    if job.status in ("completed", "failed"):
        cached = await get_cached_response(job_id)
        if cached:
            return JSONResponse(content=json.loads(cached))

    result = await db.execute(
        select(JobResult)
        .where(JobResult.job_id == job.id)
        .order_by(JobResult.created_at)
    )
    results = result.scalars().all()

    links = []
    for r in results:
        if r.links:
            links = r.links

    response_data = {
        "success": True,
        "job_id": str(job.id),
        "status": job.status,
        "url": job.config.get("url", "") if job.config else "",
        "total": job.total_pages or 0,
        "completed_pages": job.completed_pages or 0,
        "total_pages": job.total_pages or 0,
        "links": links,
        "error": job.error,
    }

    # Cache completed/failed jobs for instant subsequent loads
    if job.status in ("completed", "failed"):
        await set_cached_response(job_id, response_data)

    return response_data


@router.get(
    "/{job_id}/export",
    summary="Export map results",
    description="Download map job results in the specified format. Supports JSON and CSV exports containing discovered URLs with their titles, descriptions, last-modified dates, and priorities.",
)
async def export_map(
    job_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export map results in various formats (json, csv)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "map":
        raise NotFoundError("Map job not found")

    result = await db.execute(
        select(JobResult)
        .where(JobResult.job_id == job.id)
        .order_by(JobResult.created_at)
    )
    results = result.scalars().all()

    links = []
    for r in results:
        if r.links:
            links = r.links

    if not links:
        raise NotFoundError("No results to export")

    short_id = job_id[:8]

    if format == "json":
        content = json.dumps(links, indent=2, ensure_ascii=False)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="map-{short_id}.json"'
            },
        )

    # CSV format
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["url", "title", "description", "lastmod", "priority"])
    for link in links:
        if isinstance(link, dict):
            writer.writerow(
                [
                    link.get("url", ""),
                    link.get("title", ""),
                    link.get("description", ""),
                    link.get("lastmod", ""),
                    link.get("priority", ""),
                ]
            )
        else:
            writer.writerow([str(link), "", "", "", ""])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="map-{short_id}.csv"'},
    )
