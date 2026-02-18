import base64
import csv
import io
import json
import logging
import re
import zipfile
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, RateLimitError, BadRequestError
from app.core.rate_limiter import check_rate_limit
from app.core.metrics import batch_jobs_total
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.batch import (
    BatchScrapeRequest,
    BatchStartResponse,
    BatchItemResult,
    BatchStatusResponse,
)
from app.schemas.scrape import PageMetadata
from app.workers.batch_worker import process_batch

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(url: str) -> str:
    name = re.sub(r"https?://", "", url)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return name.strip("_")[:120] or "page"


def _build_batch_dicts(results) -> list[dict]:
    pages = []
    for r in results:
        page: dict = {"url": r.url}
        if r.markdown:
            page["markdown"] = r.markdown
        if r.html:
            page["html"] = r.html
        if r.links:
            page["links"] = r.links
        if r.screenshot_url:
            page["screenshot_base64"] = r.screenshot_url
        meta = dict(r.metadata_) if r.metadata_ else {}
        error = meta.pop("error", None)
        structured_data = meta.pop("structured_data", None)
        headings = meta.pop("headings", None)
        images = meta.pop("images", None)
        links_detail = meta.pop("links_detail", None)
        if meta:
            page["metadata"] = meta
        if structured_data:
            page["structured_data"] = structured_data
        if headings:
            page["headings"] = headings
        if images:
            page["images"] = images
        if links_detail:
            page["links_detail"] = links_detail
        if error:
            page["error"] = error
        page["success"] = error is None
        pages.append(page)
    return pages


@router.post("/scrape", response_model=BatchStartResponse)
async def start_batch_scrape(
    request: BatchScrapeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a batch scrape job for multiple URLs."""
    # Rate limiting
    allowed, _ = await check_rate_limit(
        f"rate:batch:{user.id}", settings.RATE_LIMIT_BATCH
    )
    if not allowed:
        raise RateLimitError("Batch rate limit exceeded. Try again in a minute.")

    # Build URL list
    urls = []
    if request.urls:
        urls = [u.strip() for u in request.urls if u.strip()]
    elif request.items:
        urls = [item.url for item in request.items]

    if not urls:
        raise BadRequestError("No URLs provided")

    if len(urls) > settings.MAX_BATCH_SIZE:
        raise BadRequestError(f"Maximum {settings.MAX_BATCH_SIZE} URLs per batch")

    # Create job record
    job = Job(
        user_id=user.id,
        type="batch",
        status="pending",
        config=request.model_dump(),
        total_pages=len(urls),
    )
    db.add(job)
    await db.flush()

    # Queue the batch task
    process_batch.delay(str(job.id), request.model_dump())

    batch_jobs_total.labels(status="started").inc()

    return BatchStartResponse(
        success=True,
        job_id=job.id,
        status="started",
        message=f"Batch scrape started for {len(urls)} URLs",
        total_urls=len(urls),
    )


@router.get("/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and results of a batch scrape job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "batch":
        raise NotFoundError("Batch job not found")

    data = None
    if job.status in ("pending", "running", "completed"):
        result = await db.execute(
            select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
        )
        results = result.scalars().all()

        data = []
        for r in results:
            page_metadata = None
            if r.metadata_:
                meta = dict(r.metadata_)
                meta.pop("structured_data", None)
                meta.pop("headings", None)
                meta.pop("images", None)
                meta.pop("links_detail", None)
                page_metadata = PageMetadata(
                    title=meta.get("title"),
                    description=meta.get("description"),
                    language=meta.get("language"),
                    source_url=meta.get("source_url", r.url),
                    status_code=meta.get("status_code", 200),
                    word_count=meta.get("word_count", 0),
                    reading_time_seconds=meta.get("reading_time_seconds", 0),
                    content_length=meta.get("content_length", 0),
                )

            error = r.metadata_.get("error") if r.metadata_ and "error" in r.metadata_ else None
            data.append(
                BatchItemResult(
                    url=r.url,
                    success=error is None,
                    markdown=r.markdown,
                    html=r.html,
                    links=r.links,
                    links_detail=r.metadata_.get("links_detail") if r.metadata_ else None,
                    screenshot=r.screenshot_url,
                    structured_data=r.metadata_.get("structured_data") if r.metadata_ else None,
                    headings=r.metadata_.get("headings") if r.metadata_ else None,
                    images=r.metadata_.get("images") if r.metadata_ else None,
                    metadata=page_metadata,
                    error=error,
                )
            )

    return BatchStatusResponse(
        success=True,
        job_id=job.id,
        status=job.status,
        total_urls=job.total_pages or 0,
        completed_urls=job.completed_pages or 0,
        data=data,
        error=job.error,
    )


@router.get("/{job_id}/export")
async def export_batch(
    job_id: str,
    format: str = Query("zip", pattern="^(zip|json|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export batch results in various formats (zip, json, csv)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "batch":
        raise NotFoundError("Batch job not found")

    result = await db.execute(
        select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
    )
    results = result.scalars().all()
    if not results:
        raise NotFoundError("No results to export")

    pages = _build_batch_dicts(results)
    short_id = job_id[:8]

    if format == "json":
        content = json.dumps(pages, indent=2, ensure_ascii=False)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="batch-{short_id}.json"'},
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "url", "success", "title", "status_code", "word_count",
            "description", "markdown_length", "html_length", "error",
        ])
        for p in pages:
            meta = p.get("metadata", {})
            writer.writerow([
                p["url"],
                p.get("success", True),
                meta.get("title", ""),
                meta.get("status_code", ""),
                meta.get("word_count", ""),
                meta.get("description", ""),
                len(p.get("markdown", "")),
                len(p.get("html", "")),
                p.get("error", ""),
            ])
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="batch-{short_id}.csv"'},
        )

    # ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        index = []
        for i, p in enumerate(pages):
            meta = p.get("metadata", {})
            index.append({
                "index": i + 1,
                "url": p["url"],
                "success": p.get("success", True),
                "title": meta.get("title", ""),
                "word_count": meta.get("word_count", 0),
            })
        zf.writestr("index.json", json.dumps(index, indent=2, ensure_ascii=False))

        for i, p in enumerate(pages):
            folder = f"{i + 1:03d}_{_sanitize_filename(p['url'])}"
            if p.get("markdown"):
                zf.writestr(f"{folder}/content.md", p["markdown"])
            if p.get("html"):
                zf.writestr(f"{folder}/content.html", p["html"])
            if p.get("screenshot_base64"):
                try:
                    zf.writestr(f"{folder}/screenshot.png", base64.b64decode(p["screenshot_base64"]))
                except Exception:
                    pass
            page_meta = {"url": p["url"], "success": p.get("success", True)}
            for key in ("metadata", "structured_data", "headings", "images", "links", "links_detail", "error"):
                if p.get(key):
                    page_meta[key] = p[key]
            zf.writestr(f"{folder}/metadata.json", json.dumps(page_meta, indent=2, ensure_ascii=False))

        zf.writestr("full_data.json", json.dumps(pages, indent=2, ensure_ascii=False))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="batch-{short_id}.zip"'},
    )
