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


@celery_app.task(name="app.workers.scrape_worker.process_scrape", bind=True, max_retries=2,
                 soft_time_limit=300, time_limit=360)
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

                # Scrape the URL (with timeout to prevent hanging)
                result = await asyncio.wait_for(
                    scrape_url(request, proxy_manager=proxy_manager),
                    timeout=120,
                )

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

            # Fire webhook if configured
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook
                    await send_webhook(
                        url=request.webhook_url,
                        payload={
                            "event": "job.completed",
                            "job_id": job_id,
                            "job_type": "scrape",
                            "status": "completed",
                            "url": url,
                        },
                        secret=request.webhook_secret,
                    )
                except Exception as wh_err:
                    logger.warning(f"Webhook delivery failed for scrape {job_id}: {wh_err}")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Scrape job {job_id} failed: {e}\n{tb}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = f"{e}\n{tb[-500:]}"
                    await db.commit()

            # Fire failure webhook
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook
                    await send_webhook(
                        url=request.webhook_url,
                        payload={
                            "event": "job.failed",
                            "job_id": job_id,
                            "job_type": "scrape",
                            "status": "failed",
                            "error": str(e),
                        },
                        secret=request.webhook_secret,
                    )
                except Exception:
                    pass

            raise
        finally:
            await db_engine.dispose()

    _run_async(_do_scrape())
