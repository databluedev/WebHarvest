import asyncio
import logging
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.scrape_worker.process_scrape", bind=True, max_retries=2)
def process_scrape(self, job_id: str, url: str, config: dict):
    """Process a single scrape job."""

    async def _do_scrape():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url

        from datetime import datetime, timezone

        session_factory, db_engine = create_worker_session_factory()

        try:
            # Load proxy manager if use_proxy is set
            proxy_manager = None
            request = ScrapeRequest(**config)
            if request.use_proxy:
                from app.services.proxy import ProxyManager
                async with session_factory() as db:
                    job = await db.get(Job, UUID(job_id))
                    if job:
                        proxy_manager = await ProxyManager.from_user(db, job.user_id)

            async with session_factory() as db:
                # Update job status
                job = await db.get(Job, UUID(job_id))
                if not job:
                    return

                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                await db.commit()

                # Scrape the URL
                result = await scrape_url(request, proxy_manager=proxy_manager)

                # Build rich metadata
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

                # Store result
                job_result = JobResult(
                    job_id=UUID(job_id),
                    url=url,
                    markdown=result.markdown,
                    html=result.html,
                    links=result.links if result.links else None,
                    extract=result.extract,
                    screenshot_url=result.screenshot,
                    metadata_=metadata if metadata else None,
                )
                db.add(job_result)

                job.status = "completed"
                job.completed_pages = 1
                job.total_pages = 1
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            logger.error(f"Scrape job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    await db.commit()
            raise
        finally:
            await db_engine.dispose()

    _run_async(_do_scrape())
