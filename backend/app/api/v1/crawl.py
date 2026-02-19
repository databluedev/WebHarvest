import base64
import csv
import io
import json
import logging
import re
import zipfile
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.crawl import (
    CrawlRequest,
    CrawlStartResponse,
    CrawlStatusResponse,
    CrawlPageData,
)
from app.schemas.scrape import PageMetadata
from app.workers.crawl_worker import process_crawl

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(url: str) -> str:
    """Convert a URL into a safe folder/file name."""
    name = re.sub(r"https?://", "", url)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    name = name.strip("_")[:120]
    return name or "page"


def _build_result_dicts(results) -> list[dict]:
    """Convert JobResult rows to plain dicts for export."""
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

        pages.append(page)
    return pages


@router.post("", response_model=CrawlStartResponse)
async def start_crawl(
    request: CrawlRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an asynchronous crawl job."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:crawl:{user.id}", settings.RATE_LIMIT_CRAWL
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Crawl rate limit exceeded. Try again in a minute.")

    # Cap max pages
    if request.max_pages > settings.MAX_CRAWL_PAGES:
        request.max_pages = settings.MAX_CRAWL_PAGES

    # Create job record
    job = Job(
        user_id=user.id,
        type="crawl",
        status="pending",
        config=request.model_dump(),
    )
    db.add(job)
    await db.flush()

    # Queue the crawl task
    process_crawl.delay(str(job.id), request.model_dump())

    return CrawlStartResponse(
        success=True,
        job_id=job.id,
        status="started",
        message=f"Crawl job started for {request.url}",
    )


@router.get("/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and results of a crawl job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Crawl job not found")

    # Get results (return partial results while still running)
    data = None
    if job.status in ("pending", "running", "completed", "started"):
        result = await db.execute(
            select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
        )
        results = result.scalars().all()

        data = []
        for r in results:
            # Extract base metadata fields
            page_metadata = None
            structured_data = None
            headings = None
            images = None
            links_detail = None

            if r.metadata_:
                meta = dict(r.metadata_)
                # Pop extended fields that we stored inside metadata_
                structured_data = meta.pop("structured_data", None)
                headings = meta.pop("headings", None)
                images = meta.pop("images", None)
                links_detail = meta.pop("links_detail", None)

                # Build PageMetadata from remaining fields
                page_metadata = PageMetadata(
                    title=meta.get("title"),
                    description=meta.get("description"),
                    language=meta.get("language"),
                    source_url=meta.get("source_url", r.url),
                    status_code=meta.get("status_code", 200),
                    word_count=meta.get("word_count", 0),
                    reading_time_seconds=meta.get("reading_time_seconds", 0),
                    content_length=meta.get("content_length", 0),
                    og_image=meta.get("og_image"),
                    canonical_url=meta.get("canonical_url"),
                    favicon=meta.get("favicon"),
                    robots=meta.get("robots"),
                    response_headers=meta.get("response_headers"),
                )

            data.append(
                CrawlPageData(
                    url=r.url,
                    markdown=r.markdown,
                    html=r.html,
                    links=r.links,
                    links_detail=links_detail,
                    screenshot=r.screenshot_url,  # base64 data stored here
                    structured_data=structured_data,
                    headings=headings,
                    images=images,
                    metadata=page_metadata,
                )
            )

    return CrawlStatusResponse(
        success=True,
        job_id=job.id,
        status=job.status,
        total_pages=job.total_pages,
        completed_pages=job.completed_pages,
        data=data,
        error=job.error,
    )


@router.delete("/{job_id}")
async def cancel_crawl(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running crawl job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Crawl job not found")

    if job.status in ("pending", "running"):
        job.status = "cancelled"
        return {"success": True, "message": "Crawl job cancelled"}

    return {"success": False, "message": f"Cannot cancel job with status: {job.status}"}


@router.get("/{job_id}/export")
async def export_crawl(
    job_id: str,
    format: str = Query("zip", pattern="^(zip|json|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export crawl results in various formats (zip, json, csv)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Crawl job not found")

    result = await db.execute(
        select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
    )
    results = result.scalars().all()

    if not results:
        raise NotFoundError("No results to export")

    pages = _build_result_dicts(results)
    short_id = job_id[:8]

    if format == "json":
        content = json.dumps(pages, indent=2, ensure_ascii=False)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="crawl-{short_id}.json"'},
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "url", "title", "status_code", "word_count",
            "reading_time_min", "description", "markdown_length", "html_length",
            "links_count", "has_screenshot",
        ])
        for p in pages:
            meta = p.get("metadata", {})
            reading_secs = meta.get("reading_time_seconds", 0)
            writer.writerow([
                p["url"],
                meta.get("title", ""),
                meta.get("status_code", ""),
                meta.get("word_count", ""),
                round(reading_secs / 60, 1) if reading_secs else "",
                meta.get("description", ""),
                len(p.get("markdown", "")),
                len(p.get("html", "")),
                len(p.get("links", [])),
                "yes" if p.get("screenshot_base64") else "no",
            ])
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="crawl-{short_id}.csv"'},
        )

    # ZIP format (default)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write index.json with summary (no heavy content)
        index = []
        for i, p in enumerate(pages):
            meta = p.get("metadata", {})
            index.append({
                "index": i + 1,
                "url": p["url"],
                "title": meta.get("title", ""),
                "status_code": meta.get("status_code", ""),
                "word_count": meta.get("word_count", 0),
            })
        zf.writestr("index.json", json.dumps(index, indent=2, ensure_ascii=False))

        for i, p in enumerate(pages):
            folder = f"{i + 1:03d}_{_sanitize_filename(p['url'])}"

            # Markdown file
            if p.get("markdown"):
                zf.writestr(f"{folder}/content.md", p["markdown"])

            # HTML file
            if p.get("html"):
                zf.writestr(f"{folder}/content.html", p["html"])

            # Screenshot PNG
            if p.get("screenshot_base64"):
                try:
                    img_data = base64.b64decode(p["screenshot_base64"])
                    zf.writestr(f"{folder}/screenshot.jpg", img_data)
                except Exception:
                    pass

            # Metadata JSON
            page_meta = {}
            for key in ("metadata", "structured_data", "headings", "images", "links", "links_detail"):
                if p.get(key):
                    page_meta[key] = p[key]
            page_meta["url"] = p["url"]
            zf.writestr(
                f"{folder}/metadata.json",
                json.dumps(page_meta, indent=2, ensure_ascii=False),
            )

        # Full data JSON as well
        zf.writestr("full_data.json", json.dumps(pages, indent=2, ensure_ascii=False))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="crawl-{short_id}.zip"'},
    )
