import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.batch_worker.process_batch",
    bind=True,
    max_retries=1,
    soft_time_limit=1800,
    time_limit=1860,
)
def process_batch(self, job_id: str, config: dict):
    """Process a batch scrape job — scrape multiple URLs concurrently."""

    async def _do_batch():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.batch import BatchScrapeRequest
        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url
        from app.services.llm_extract import extract_with_llm
        from app.services.dedup import deduplicate_urls

        session_factory, db_engine = create_worker_session_factory()
        request = BatchScrapeRequest(**config)

        # Build URL list with per-URL overrides
        url_configs = []
        # Shared fields to propagate to each ScrapeRequest
        _shared = {
            "headers": getattr(request, "headers", None),
            "cookies": getattr(request, "cookies", None),
            "mobile": getattr(request, "mobile", False),
        }

        if request.items:
            # Deduplicate items by URL
            seen_urls = set()
            for item in request.items:
                from app.services.dedup import normalize_url

                norm = normalize_url(item.url)
                if norm in seen_urls:
                    continue
                seen_urls.add(norm)
                url_configs.append(
                    {
                        "url": item.url,
                        "formats": item.formats or request.formats,
                        "only_main_content": item.only_main_content
                        if item.only_main_content is not None
                        else request.only_main_content,
                        "wait_for": item.wait_for
                        if item.wait_for is not None
                        else request.wait_for,
                        "timeout": item.timeout
                        if item.timeout is not None
                        else request.timeout,
                        **_shared,
                    }
                )
        elif request.urls:
            # Deduplicate URL list
            deduped = deduplicate_urls(request.urls)
            for url in deduped:
                url_configs.append(
                    {
                        "url": url,
                        "formats": request.formats,
                        "only_main_content": request.only_main_content,
                        "wait_for": request.wait_for,
                        "timeout": request.timeout,
                        **_shared,
                    }
                )

        if not url_configs:
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = "No URLs to scrape"
                await db.commit()
            await db_engine.dispose()
            return

        # Load proxy manager if needed
        proxy_manager = None
        if request.use_proxy:
            from app.services.proxy import ProxyManager

            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    proxy_manager = await ProxyManager.from_user(db, job.user_id)

        # Update job to running and capture user_id
        user_id = None
        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                await db_engine.dispose()
                return
            user_id = job.user_id
            job.status = "running"
            job.total_pages = len(url_configs)
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        PER_URL_TIMEOUT = 120  # seconds per URL

        semaphore = asyncio.Semaphore(request.concurrency)
        completed_count = 0

        async def scrape_one(url_config: dict):
            nonlocal completed_count
            async with semaphore:
                url = url_config["url"]
                r = None
                try:
                    scrape_request = ScrapeRequest(**url_config)
                    result = await asyncio.wait_for(
                        scrape_url(scrape_request, proxy_manager=proxy_manager),
                        timeout=PER_URL_TIMEOUT,
                    )

                    metadata = {}
                    if result.metadata:
                        metadata = result.metadata.model_dump(exclude_none=True)
                    if result.structured_data:
                        metadata["structured_data"] = result.structured_data
                    if result.headings:
                        metadata["headings"] = result.headings
                    if result.images:
                        metadata["images"] = result.images
                    if result.links_detail:
                        metadata["links_detail"] = result.links_detail

                    # LLM extraction if configured
                    extract_data = None
                    if request.extract and result.markdown:
                        try:
                            async with session_factory() as llm_db:
                                extract_data = await asyncio.wait_for(
                                    extract_with_llm(
                                        db=llm_db,
                                        user_id=user_id,
                                        content=result.markdown,
                                        prompt=request.extract.prompt,
                                        schema=request.extract.schema_,
                                    ),
                                    timeout=90,
                                )
                        except Exception as e:
                            logger.warning(f"LLM extraction failed for {url}: {e}")

                    r = {
                        "url": url,
                        "markdown": result.markdown,
                        "html": result.html,
                        "links": result.links if result.links else None,
                        "screenshot": result.screenshot,
                        "extract": extract_data,
                        "metadata": metadata,
                        "error": None,
                    }
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Batch scrape timed out for {url} after {PER_URL_TIMEOUT}s"
                    )
                    r = {
                        "url": url,
                        "markdown": None,
                        "html": None,
                        "links": None,
                        "screenshot": None,
                        "extract": None,
                        "metadata": {"error": f"Timed out after {PER_URL_TIMEOUT}s"},
                        "error": f"Timed out after {PER_URL_TIMEOUT}s",
                    }
                except Exception as e:
                    logger.warning(f"Batch scrape failed for {url}: {e}")
                    r = {
                        "url": url,
                        "markdown": None,
                        "html": None,
                        "links": None,
                        "screenshot": None,
                        "extract": None,
                        "metadata": {"error": str(e)},
                        "error": str(e),
                    }

                # Save result immediately (progressive)
                async with session_factory() as db:
                    job_result = JobResult(
                        job_id=UUID(job_id),
                        url=r["url"],
                        markdown=r["markdown"],
                        html=r["html"],
                        links=r["links"],
                        extract=r.get("extract"),
                        metadata_=r["metadata"] if r["metadata"] else None,
                        screenshot_url=r["screenshot"],
                    )
                    db.add(job_result)
                    completed_count += 1
                    job = await db.get(Job, UUID(job_id))
                    if job:
                        job.completed_pages = completed_count
                    await db.commit()

        try:
            tasks = [scrape_one(uc) for uc in url_configs]
            await asyncio.gather(*tasks)

            # Mark job completed
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.completed_pages = completed_count
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            # Send webhook if configured
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook

                    async with session_factory() as db:
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            await send_webhook(
                                url=request.webhook_url,
                                payload={
                                    "event": "job.completed",
                                    "job_id": job_id,
                                    "job_type": "batch",
                                    "status": job.status,
                                    "total_pages": job.total_pages,
                                    "completed_pages": job.completed_pages,
                                    "created_at": job.created_at.isoformat()
                                    if job.created_at
                                    else None,
                                    "completed_at": job.completed_at.isoformat()
                                    if job.completed_at
                                    else None,
                                },
                                secret=request.webhook_secret,
                            )
                except Exception as e:
                    logger.warning(f"Webhook delivery failed for batch {job_id}: {e}")

        except Exception as e:
            logger.error(f"Batch job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()

            # Send failure webhook
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook

                    await send_webhook(
                        url=request.webhook_url,
                        payload={
                            "event": "job.failed",
                            "job_id": job_id,
                            "job_type": "batch",
                            "status": "failed",
                            "error": str(e),
                        },
                        secret=request.webhook_secret,
                    )
                except Exception:
                    pass
        finally:
            await db_engine.dispose()

    _run_async(_do_batch())
