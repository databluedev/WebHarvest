"""Standalone /extract endpoint for LLM-powered data extraction."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.rate_limiter import check_rate_limit_full
from app.config import settings
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User
from app.schemas.extract import (
    ExtractRequest,
    ExtractResult,
    ExtractResponse,
    ExtractStartResponse,
    ExtractStatusResponse,
)
from app.services.llm_extract import extract_with_llm
from app.services.quota import check_quota, increment_usage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=None)
async def extract(
    request: ExtractRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract structured data from content or URLs using LLM.

    Supports three modes:
    1. **Direct content**: Pass `content` or `html` for immediate extraction
    2. **Single URL**: Pass `url` to scrape + extract synchronously
    3. **Multi URL**: Pass `urls` to scrape + extract asynchronously (returns job_id)
    """
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:extract:{user.id}", settings.RATE_LIMIT_SCRAPE
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        from app.core.exceptions import RateLimitError
        raise RateLimitError("Extract rate limit exceeded. Try again in a minute.")

    # Validate input
    if not request.content and not request.html and not request.url and not request.urls:
        raise BadRequestError("Provide at least one of: content, html, url, or urls")
    if not request.prompt and not request.schema_:
        raise BadRequestError("Provide at least one of: prompt or schema")

    # Check quota
    await check_quota(db, user.id, "extract")

    # Mode 3: Multi-URL async extraction
    if request.urls and len(request.urls) > 1:
        return await _start_async_extract(request, user, db)

    # Modes 1 & 2: Synchronous extraction
    content = request.content or ""

    # If HTML provided, convert to markdown
    if not content and request.html:
        from app.services.content import html_to_markdown, extract_main_content
        html = request.html
        if request.only_main_content:
            html = extract_main_content(html, "")
        content = html_to_markdown(html)

    # If URL provided, scrape first
    source_url = request.url
    if not content and (request.url or (request.urls and len(request.urls) == 1)):
        url = request.url or request.urls[0]
        source_url = url

        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url

        proxy_manager = None
        if request.use_proxy:
            from app.services.proxy import ProxyManager
            proxy_manager = await ProxyManager.from_user(db, user.id)

        scrape_request = ScrapeRequest(
            url=url,
            formats=["markdown"],
            only_main_content=request.only_main_content,
            wait_for=request.wait_for,
            timeout=request.timeout,
            use_proxy=request.use_proxy,
            headers=request.headers,
            cookies=request.cookies,
        )

        try:
            result = await asyncio.wait_for(
                scrape_url(scrape_request, proxy_manager=proxy_manager),
                timeout=settings.SCRAPE_API_TIMEOUT,
            )
            content = result.markdown or ""
            if not content and result.html:
                from app.services.content import html_to_markdown, extract_main_content
                content = html_to_markdown(
                    extract_main_content(result.html, url) if request.only_main_content else result.html
                )
        except asyncio.TimeoutError:
            return ExtractResponse(
                success=False,
                error=f"Scrape timed out for {url}",
            )
        except Exception as e:
            return ExtractResponse(
                success=False,
                error=f"Failed to scrape {url}: {str(e)}",
            )

    if not content:
        return ExtractResponse(
            success=False,
            error="No content available for extraction",
        )

    # Extract with LLM
    try:
        extract_result = await extract_with_llm(
            db=db,
            user_id=user.id,
            content=content,
            prompt=request.prompt,
            schema=request.schema_,
            provider=request.provider,
        )

        # Increment usage
        await increment_usage(db, user.id, "extract")
        await db.commit()

        return ExtractResponse(
            success=True,
            data=ExtractResult(
                url=source_url,
                extract=extract_result,
                content_length=len(content),
            ),
        )

    except BadRequestError:
        raise
    except Exception as e:
        logger.error(f"Extract failed: {e}")
        return ExtractResponse(
            success=False,
            error=str(e),
        )


async def _start_async_extract(
    request: ExtractRequest,
    user: User,
    db: AsyncSession,
) -> ExtractStartResponse:
    """Start an async multi-URL extraction job."""
    from app.workers.extract_worker import process_extract

    job = Job(
        user_id=user.id,
        type="extract",
        status="pending",
        config=request.model_dump(),
        total_pages=len(request.urls),
    )
    db.add(job)
    await db.flush()

    # Queue the extraction task
    process_extract.delay(str(job.id), request.model_dump())

    return ExtractStartResponse(
        success=True,
        job_id=str(job.id),
        status="started",
        message=f"Extraction started for {len(request.urls)} URLs",
        total_urls=len(request.urls),
    )


@router.get("/{job_id}", response_model=ExtractStatusResponse)
async def get_extract_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of an async extraction job."""
    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id or job.type != "extract":
        raise NotFoundError("Extract job not found")

    result = await db.execute(
        select(JobResult).where(JobResult.job_id == job.id).order_by(JobResult.created_at)
    )
    results = result.scalars().all()

    data = []
    for r in results:
        meta = r.metadata_ or {}
        data.append(ExtractResult(
            url=r.url,
            extract=r.extract,
            content_length=meta.get("content_length", 0),
            error=meta.get("error"),
        ))

    return ExtractStatusResponse(
        success=True,
        job_id=str(job.id),
        status=job.status,
        total_urls=job.total_pages,
        completed_urls=job.completed_pages,
        data=data if data else None,
        error=job.error,
    )
