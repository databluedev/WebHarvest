import asyncio
import base64
import csv
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.rate_limiter import check_rate_limit_full
from app.core.metrics import scrape_requests_total
from app.core.job_cache import get_cached_response, set_cached_response
from app.core.cache import get_cached_scrape
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.scrape import ScrapeRequest, ScrapeResponse, ScrapeData, PageMetadata
from app.services.scraper import scrape_url, classify_error
from app.services.llm_extract import extract_with_llm
from app.services.quota import check_quota, increment_usage

router = APIRouter()
logger = logging.getLogger(__name__)

# Global concurrency limiter — prevents OOM when many requests arrive simultaneously.
# Requests beyond this limit wait in queue instead of all running at once.
_scrape_semaphore: asyncio.Semaphore | None = None


def _get_scrape_semaphore() -> asyncio.Semaphore:
    global _scrape_semaphore
    if _scrape_semaphore is None:
        _scrape_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SCRAPES)
    return _scrape_semaphore


def _sanitize_filename(url: str) -> str:
    name = re.sub(r"https?://", "", url)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    name = name.strip("_")[:120]
    return name or "page"


def _build_result_dicts(results) -> list[dict]:
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
        if r.extract:
            page["extract"] = r.extract

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


@router.post(
    "",
    response_model=ScrapeResponse,
    response_model_exclude_none=True,
    summary="Scrape a single URL",
    description="Extract content from a URL using the 5-tier scraping pipeline. Returns markdown, HTML, links, screenshots, structured data, and more depending on requested formats. Supports LLM extraction, proxy routing, and browser actions.",
    response_description="Scraped content with metadata and job ID",
)
async def scrape(
    request: ScrapeRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scrape a single URL and return content in requested formats."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:scrape:{user.id}", settings.RATE_LIMIT_SCRAPE
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        from app.core.exceptions import RateLimitError

        raise RateLimitError("Scrape rate limit exceeded. Try again in a minute.")

    # API-level cache check — return instantly without job/quota/semaphore
    use_cache = (
        not request.actions
        and "screenshot" not in request.formats
        and not request.extract
    )
    if use_cache:
        cached = await get_cached_scrape(request.url, request.formats)
        if cached:
            scrape_requests_total.labels(status="success").inc()
            return ScrapeResponse(success=True, data=ScrapeData(**cached))

    # Quota check
    await check_quota(db, user.id, "scrape")

    # Create job record
    job = Job(
        user_id=user.id,
        type="scrape",
        status="running",
        config=request.model_dump(),
        total_pages=1,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    try:
        # Load proxy manager if use_proxy is set
        proxy_manager = None
        if getattr(request, "use_proxy", False):
            from app.services.proxy import ProxyManager

            proxy_manager = await ProxyManager.from_user(db, user.id)

        # Acquire concurrency slot — prevents OOM from too many parallel scrapes
        sem = _get_scrape_semaphore()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=30)
        except asyncio.TimeoutError:
            job.status = "failed"
            job.error = "Server is at capacity. Please retry in a few seconds."
            job.completed_at = datetime.now(timezone.utc)
            scrape_requests_total.labels(status="error").inc()
            return ScrapeResponse(
                success=False, error=job.error, error_code="TIMEOUT", job_id=str(job.id)
            )

        try:
            # Scrape with overall timeout to prevent hanging
            result = await asyncio.wait_for(
                scrape_url(request, proxy_manager=proxy_manager),
                timeout=settings.SCRAPE_API_TIMEOUT,
            )
        except asyncio.TimeoutError:
            job.status = "failed"
            job.error = f"Scrape timed out after {settings.SCRAPE_API_TIMEOUT}s. The site may be too slow or heavily protected."
            job.completed_at = datetime.now(timezone.utc)
            scrape_requests_total.labels(status="error").inc()
            return ScrapeResponse(
                success=False, error=job.error, error_code="TIMEOUT", job_id=str(job.id)
            )
        finally:
            sem.release()

        # LLM extraction if requested
        if request.extract and result.markdown:
            extract_result = await extract_with_llm(
                db=db,
                user_id=user.id,
                content=result.markdown,
                prompt=request.extract.prompt,
                schema=request.extract.schema_,
            )
            result.extract = extract_result

        # Persist the result — only include data the user requested
        _req_fmts = set(request.formats)
        metadata_dict = result.metadata.model_dump() if result.metadata else {}
        if result.structured_data and (not _req_fmts or "structured_data" in _req_fmts):
            metadata_dict["structured_data"] = result.structured_data
        if result.headings and (not _req_fmts or "headings" in _req_fmts):
            metadata_dict["headings"] = result.headings
        if result.images and (not _req_fmts or "images" in _req_fmts):
            metadata_dict["images"] = result.images
        if result.links_detail and (not _req_fmts or "links" in _req_fmts):
            metadata_dict["links_detail"] = result.links_detail

        job_result = JobResult(
            job_id=job.id,
            url=request.url,
            markdown=result.markdown if not _req_fmts or "markdown" in _req_fmts else None,
            html=result.html if not _req_fmts or "html" in _req_fmts else None,
            links=result.links if not _req_fmts or "links" in _req_fmts else None,
            extract=result.extract,
            metadata_=metadata_dict,
            screenshot_url=result.screenshot if not _req_fmts or "screenshot" in _req_fmts else None,
        )
        db.add(job_result)

        # Check if we actually got any content
        has_content = any(
            [
                result.markdown,
                result.html,
                result.raw_html,
                result.screenshot,
                result.links,
            ]
        )

        if has_content:
            job.status = "completed"
            job.completed_pages = 1
            job.completed_at = datetime.now(timezone.utc)
            scrape_requests_total.labels(status="success").inc()
            await increment_usage(db, user.id, "scrape", pages=1)
            resp = ScrapeResponse(success=True, data=result, job_id=str(job.id))
        else:
            job.status = "failed"
            job.error = "All scraping strategies failed — the site may be blocking requests from this server. Try enabling a residential proxy."
            job.completed_at = datetime.now(timezone.utc)
            scrape_requests_total.labels(status="error").inc()
            error_code = classify_error(
                job.error,
                html=result.raw_html or result.html,
                status_code=result.metadata.status_code if result.metadata else 0,
            )
            resp = ScrapeResponse(
                success=False,
                data=result,
                error=job.error,
                error_code=error_code,
                job_id=str(job.id),
            )

        # Fire webhook if configured (best-effort, non-blocking)
        if request.webhook_url:
            try:
                from app.services.webhook import send_webhook

                await send_webhook(
                    url=request.webhook_url,
                    payload={
                        "event": f"job.{job.status}",
                        "job_id": str(job.id),
                        "job_type": "scrape",
                        "status": job.status,
                        "url": request.url,
                        "completed_at": job.completed_at.isoformat()
                        if job.completed_at
                        else None,
                    },
                    secret=request.webhook_secret,
                )
            except Exception as wh_err:
                logger.warning(f"Webhook delivery failed for scrape {job.id}: {wh_err}")

        return resp

    except BadRequestError:
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        raise
    except Exception as e:
        logger.error(f"Scrape failed for {request.url}: {e}")
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
        scrape_requests_total.labels(status="error").inc()
        error_code = classify_error(str(e))

        # Fire failure webhook
        if request.webhook_url:
            try:
                from app.services.webhook import send_webhook

                await send_webhook(
                    url=request.webhook_url,
                    payload={
                        "event": "job.failed",
                        "job_id": str(job.id),
                        "job_type": "scrape",
                        "status": "failed",
                        "url": request.url,
                        "error": str(e),
                    },
                    secret=request.webhook_secret,
                )
            except Exception:
                pass

        return ScrapeResponse(
            success=False, error=str(e), error_code=error_code, job_id=str(job.id)
        )


@router.get(
    "/{job_id}",
    summary="Get scrape result",
    description="Retrieve the status and content of a previously submitted scrape job by its ID.",
)
async def get_scrape_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and result of a scrape job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "scrape":
        raise NotFoundError("Scrape job not found")

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

    # Determine which formats the user originally requested
    requested_formats = set()
    if job.config:
        requested_formats = set(job.config.get("formats", []))

    data = []
    for r in results:
        page_metadata = None
        structured_data = None
        headings = None
        images = None
        links_detail = None

        if r.metadata_:
            meta = dict(r.metadata_)
            structured_data = meta.pop("structured_data", None)
            headings = meta.pop("headings", None)
            images = meta.pop("images", None)
            links_detail = meta.pop("links_detail", None)

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

        # Only include fields the user actually requested
        page: dict = {"id": str(r.id), "url": r.url}
        if not requested_formats or "markdown" in requested_formats:
            page["markdown"] = r.markdown
        if not requested_formats or "html" in requested_formats:
            page["html"] = r.html
        if not requested_formats or "links" in requested_formats:
            page["links"] = r.links
            if links_detail:
                page["links_detail"] = links_detail
        if not requested_formats or "screenshot" in requested_formats:
            if r.screenshot_url:
                page["screenshot"] = r.screenshot_url
        if not requested_formats or "structured_data" in requested_formats:
            if structured_data:
                page["structured_data"] = structured_data
        if not requested_formats or "headings" in requested_formats:
            if headings:
                page["headings"] = headings
        if not requested_formats or "images" in requested_formats:
            if images:
                page["images"] = images
        if r.extract:
            page["extract"] = r.extract
        if page_metadata:
            page["metadata"] = page_metadata.model_dump(exclude_none=True)
        data.append(page)

    response_data = {
        "success": True,
        "job_id": str(job.id),
        "status": job.status,
        "total_pages": job.total_pages,
        "completed_pages": job.completed_pages,
        "data": data,
    }
    if job.error:
        response_data["error"] = job.error

    # Cache completed/failed jobs for instant subsequent loads
    if job.status in ("completed", "failed"):
        await set_cached_response(job_id, response_data)

    return response_data


@router.get(
    "/{job_id}/export",
    summary="Export scrape results",
    description="Download scrape results as JSON, CSV, or ZIP archive with markdown, HTML, and screenshots.",
)
async def export_scrape(
    job_id: str,
    format: str = Query("zip", pattern="^(zip|json|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export scrape results in various formats (zip, json, csv)."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "scrape":
        raise NotFoundError("Scrape job not found")

    result = await db.execute(
        select(JobResult)
        .where(JobResult.job_id == job.id)
        .order_by(JobResult.created_at)
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
            headers={
                "Content-Disposition": f'attachment; filename="scrape-{short_id}.json"'
            },
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "url",
                "title",
                "status_code",
                "word_count",
                "reading_time_min",
                "description",
                "markdown_length",
                "html_length",
                "links_count",
                "has_screenshot",
            ]
        )
        for p in pages:
            meta = p.get("metadata", {})
            reading_secs = meta.get("reading_time_seconds", 0)
            writer.writerow(
                [
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
                ]
            )
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="scrape-{short_id}.csv"'
            },
        )

    # ZIP format (default)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, p in enumerate(pages):
            folder = _sanitize_filename(p["url"])

            if p.get("markdown"):
                zf.writestr(f"{folder}/content.md", p["markdown"])
            if p.get("html"):
                zf.writestr(f"{folder}/content.html", p["html"])
            if p.get("screenshot_base64"):
                try:
                    img_data = base64.b64decode(p["screenshot_base64"])
                    zf.writestr(f"{folder}/screenshot.jpg", img_data)
                except Exception:
                    pass

            page_meta = {}
            for key in (
                "metadata",
                "structured_data",
                "headings",
                "images",
                "links",
                "links_detail",
                "extract",
            ):
                if p.get(key):
                    page_meta[key] = p[key]
            page_meta["url"] = p["url"]
            zf.writestr(
                f"{folder}/metadata.json",
                json.dumps(page_meta, indent=2, ensure_ascii=False),
            )

        zf.writestr("full_data.json", json.dumps(pages, indent=2, ensure_ascii=False))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="scrape-{short_id}.zip"'
        },
    )
