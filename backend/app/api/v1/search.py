import base64
import csv
import io
import json
import logging
import re
import zipfile
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.core.metrics import search_jobs_total
from app.core.job_cache import get_cached_response, set_cached_response
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.search import (
    SearchRequest,
    SearchStartResponse,
    SearchResultItem,
    SearchStatusResponse,
)
from app.schemas.scrape import PageMetadata
from app.workers.search_worker import process_search
from app.services.quota import check_quota, increment_usage

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(url: str) -> str:
    name = re.sub(r"https?://", "", url)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return name.strip("_")[:120] or "page"


def _build_search_dicts(results) -> list[dict]:
    pages = []
    for r in results:
        meta = dict(r.metadata_) if r.metadata_ else {}
        page: dict = {
            "url": r.url,
            "title": meta.get("title", ""),
            "snippet": meta.get("snippet", ""),
            "success": "error" not in meta,
        }
        if r.markdown:
            page["markdown"] = r.markdown
        if r.html:
            page["html"] = r.html
        if r.links:
            page["links"] = r.links
        if r.screenshot_url:
            page["screenshot_base64"] = r.screenshot_url
        error = meta.pop("error", None)
        title = meta.pop("title", None)
        snippet = meta.pop("snippet", None)
        meta.pop("structured_data", None)
        meta.pop("headings", None)
        meta.pop("images", None)
        meta.pop("links_detail", None)
        if meta:
            page["metadata"] = meta
        if error:
            page["error"] = error
            page["success"] = False
        pages.append(page)
    return pages


@router.post("", response_model=SearchStartResponse)
async def start_search(
    request: SearchRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search the web and scrape top results."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:search:{user.id}", settings.RATE_LIMIT_SEARCH
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Search rate limit exceeded. Try again in a minute.")

    # Quota check
    await check_quota(db, user.id, "search")

    if request.num_results > settings.MAX_SEARCH_RESULTS:
        request.num_results = settings.MAX_SEARCH_RESULTS

    # Create job record
    job = Job(
        user_id=user.id,
        type="search",
        status="pending",
        config=request.model_dump(),
        total_pages=request.num_results,
    )
    db.add(job)
    await db.flush()

    # Queue the search task
    process_search.delay(str(job.id), request.model_dump())

    search_jobs_total.labels(status="started").inc()

    return SearchStartResponse(
        success=True,
        job_id=job.id,
        status="started",
        message=f'Search started for "{request.query}"',
    )


@router.get("/{job_id}", response_model=SearchStatusResponse)
async def get_search_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and results of a search job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "search":
        raise NotFoundError("Search job not found")

    # Return cached response instantly for completed/failed jobs
    if job.status in ("completed", "failed"):
        cached = await get_cached_response(job_id)
        if cached:
            return JSONResponse(content=json.loads(cached))

    query = job.config.get("query", "") if job.config else ""

    data = None
    if job.status in ("pending", "running", "completed"):
        result = await db.execute(
            select(JobResult)
            .where(JobResult.job_id == job.id)
            .order_by(JobResult.created_at)
        )
        results = result.scalars().all()

        data = []
        for r in results:
            meta = r.metadata_ or {}
            page_metadata = None
            if meta:
                clean_meta = {k: v for k, v in meta.items() if k not in ("title", "snippet", "error", "structured_data", "headings", "images", "links_detail")}
                if clean_meta.get("source_url"):
                    page_metadata = PageMetadata(
                        source_url=clean_meta.get("source_url", r.url),
                        status_code=clean_meta.get("status_code", 200),
                        word_count=clean_meta.get("word_count", 0),
                        reading_time_seconds=clean_meta.get("reading_time_seconds", 0),
                        content_length=clean_meta.get("content_length", 0),
                    )

            data.append(
                SearchResultItem(
                    id=str(r.id),
                    url=r.url,
                    title=meta.get("title"),
                    snippet=meta.get("snippet"),
                    success="error" not in meta,
                    markdown=r.markdown,
                    html=r.html,
                    links=r.links,
                    links_detail=meta.get("links_detail"),
                    screenshot=r.screenshot_url,
                    structured_data=meta.get("structured_data"),
                    headings=meta.get("headings"),
                    images=meta.get("images"),
                    extract=r.extract,
                    metadata=page_metadata,
                    error=meta.get("error"),
                )
            )

    response_obj = SearchStatusResponse(
        success=True,
        job_id=job.id,
        status=job.status,
        query=query,
        total_results=job.total_pages,
        completed_results=job.completed_pages,
        data=data,
        error=job.error,
    )

    # Cache completed/failed jobs for instant subsequent loads
    if job.status in ("completed", "failed"):
        await set_cached_response(job_id, response_obj.model_dump())

    return response_obj


@router.get("/{job_id}/export")
async def export_search(
    job_id: str,
    format: str = Query("zip", pattern="^(zip|json|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export search results in various formats (zip, json, csv)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "search":
        raise NotFoundError("Search job not found")

    query = job.config.get("query", "") if job.config else ""

    result = await db.execute(
        select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
    )
    results = result.scalars().all()
    if not results:
        raise NotFoundError("No results to export")

    pages = _build_search_dicts(results)
    short_id = job_id[:8]

    if format == "json":
        export_data = {"query": query, "results": pages}
        content = json.dumps(export_data, indent=2, ensure_ascii=False)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="search-{short_id}.json"'},
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "url", "title", "snippet", "success", "word_count",
            "markdown_length", "error",
        ])
        for p in pages:
            meta = p.get("metadata", {})
            writer.writerow([
                p["url"],
                p.get("title", ""),
                p.get("snippet", ""),
                p.get("success", True),
                meta.get("word_count", ""),
                len(p.get("markdown", "")),
                p.get("error", ""),
            ])
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="search-{short_id}.csv"'},
        )

    # ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        index = [{"query": query}]
        for i, p in enumerate(pages):
            index.append({
                "index": i + 1,
                "url": p["url"],
                "title": p.get("title", ""),
                "snippet": p.get("snippet", ""),
                "success": p.get("success", True),
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
                    zf.writestr(f"{folder}/screenshot.jpg", base64.b64decode(p["screenshot_base64"]))
                except Exception:
                    pass
            page_meta = {
                "url": p["url"],
                "title": p.get("title", ""),
                "snippet": p.get("snippet", ""),
                "success": p.get("success", True),
            }
            if p.get("metadata"):
                page_meta["metadata"] = p["metadata"]
            if p.get("error"):
                page_meta["error"] = p["error"]
            zf.writestr(f"{folder}/metadata.json", json.dumps(page_meta, indent=2, ensure_ascii=False))

        export_data = {"query": query, "results": pages}
        zf.writestr("full_data.json", json.dumps(export_data, indent=2, ensure_ascii=False))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="search-{short_id}.zip"'},
    )
