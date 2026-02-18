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


@celery_app.task(name="app.workers.batch_worker.process_batch", bind=True, max_retries=1)
def process_batch(self, job_id: str, config: dict):
    """Process a batch scrape job — scrape multiple URLs concurrently."""

    async def _do_batch():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.batch import BatchScrapeRequest
        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url

        session_factory, db_engine = create_worker_session_factory()
        request = BatchScrapeRequest(**config)

        # Build URL list with per-URL overrides
        url_configs = []
        if request.items:
            for item in request.items:
                url_configs.append({
                    "url": item.url,
                    "formats": item.formats or request.formats,
                    "only_main_content": item.only_main_content if item.only_main_content is not None else request.only_main_content,
                    "wait_for": item.wait_for if item.wait_for is not None else request.wait_for,
                    "timeout": item.timeout if item.timeout is not None else request.timeout,
                })
        elif request.urls:
            for url in request.urls:
                url = url.strip()
                if url:
                    url_configs.append({
                        "url": url,
                        "formats": request.formats,
                        "only_main_content": request.only_main_content,
                        "wait_for": request.wait_for,
                        "timeout": request.timeout,
                    })

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

        # Update job to running
        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                await db_engine.dispose()
                return
            job.status = "running"
            job.total_pages = len(url_configs)
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        semaphore = asyncio.Semaphore(request.concurrency)
        completed_count = 0

        async def scrape_one(url_config: dict) -> dict:
            nonlocal completed_count
            async with semaphore:
                try:
                    scrape_request = ScrapeRequest(**url_config)
                    result = await scrape_url(scrape_request, proxy_manager=proxy_manager)

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

                    return {
                        "url": url_config["url"],
                        "markdown": result.markdown,
                        "html": result.html,
                        "links": result.links if result.links else None,
                        "screenshot": result.screenshot,
                        "metadata": metadata,
                        "error": None,
                    }
                except Exception as e:
                    logger.warning(f"Batch scrape failed for {url_config['url']}: {e}")
                    return {
                        "url": url_config["url"],
                        "markdown": None,
                        "html": None,
                        "links": None,
                        "screenshot": None,
                        "metadata": {"error": str(e)},
                        "error": str(e),
                    }

        try:
            tasks = [scrape_one(uc) for uc in url_configs]
            results = await asyncio.gather(*tasks)

            # Store all results
            async with session_factory() as db:
                for r in results:
                    job_result = JobResult(
                        job_id=UUID(job_id),
                        url=r["url"],
                        markdown=r["markdown"],
                        html=r["html"],
                        links=r["links"],
                        metadata_=r["metadata"] if r["metadata"] else None,
                        screenshot_url=r["screenshot"],
                    )
                    db.add(job_result)

                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.completed_pages = len(results)
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            logger.error(f"Batch job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()
        finally:
            await db_engine.dispose()

    _run_async(_do_batch())
