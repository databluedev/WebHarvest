import asyncio
import logging
import time
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_WORKER_NAME = "scrape"


def _run_async(coro):
    """Run an async function from a sync Celery task."""
    from app.services.scraper import reset_pool_state_sync
    reset_pool_state_sync()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            from app.services.scraper import cleanup_async_pools
            loop.run_until_complete(cleanup_async_pools())
        except Exception:
            pass
        loop.close()


@celery_app.task(
    name="app.workers.scrape_worker.process_scrape",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    dont_autoretry_for=(ValueError, KeyError, TypeError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=300,
    time_limit=360,
)
def process_scrape(self, job_id: str, url: str, config: dict):
    """Process a single scrape job."""
    from app.core.metrics import worker_task_total, worker_task_duration_seconds, worker_active_tasks

    _start = time.monotonic()
    worker_active_tasks.labels(worker=_WORKER_NAME).inc()

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
                    # Safety: DB commit may still be in-flight — retry once
                    await asyncio.sleep(2)
                    job = await db.get(Job, UUID(job_id))
                if not job:
                    logger.error(f"Scrape job {job_id} not found in DB — aborting")
                    return

                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                await db.commit()

                # Scrape the URL (with timeout to prevent hanging)
                result = await asyncio.wait_for(
                    scrape_url(request, proxy_manager=proxy_manager),
                    timeout=120,
                )

                # Build rich metadata — only include data the user requested
                _req_fmts = set(request.formats)
                metadata = {}
                if result.metadata:
                    metadata = result.metadata.model_dump(exclude_none=True)
                if result.structured_data and (not _req_fmts or "structured_data" in _req_fmts):
                    metadata["structured_data"] = result.structured_data
                if result.headings and (not _req_fmts or "headings" in _req_fmts):
                    metadata["headings"] = result.headings
                if result.images and (not _req_fmts or "images" in _req_fmts):
                    metadata["images"] = result.images
                if result.links_detail and (not _req_fmts or "links" in _req_fmts):
                    metadata["links_detail"] = result.links_detail

                # Store result — only include fields the user requested
                job_result = JobResult(
                    job_id=UUID(job_id),
                    url=url,
                    markdown=result.markdown if not _req_fmts or "markdown" in _req_fmts else None,
                    html=result.html if not _req_fmts or "html" in _req_fmts else None,
                    links=result.links if result.links and (not _req_fmts or "links" in _req_fmts) else None,
                    extract=result.extract,
                    screenshot_url=result.screenshot if not _req_fmts or "screenshot" in _req_fmts else None,
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
                    logger.warning(
                        f"Webhook delivery failed for scrape {job_id}: {wh_err}"
                    )

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

    try:
        _run_async(_do_scrape())
        worker_task_total.labels(worker=_WORKER_NAME, status="success").inc()
    except Exception:
        worker_task_total.labels(worker=_WORKER_NAME, status="failure").inc()
        raise
    finally:
        worker_active_tasks.labels(worker=_WORKER_NAME).dec()
        worker_task_duration_seconds.labels(worker=_WORKER_NAME).observe(
            time.monotonic() - _start
        )
