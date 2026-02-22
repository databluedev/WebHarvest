import asyncio
import logging
import time as _time_mod
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_WORKER_NAME = "map"


def _run_async(coro):
    from app.services.scraper import reset_pool_state_sync
    reset_pool_state_sync()

    loop = asyncio.new_event_loop()
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
    name="app.workers.map_worker.process_map",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def process_map(self, job_id: str, config: dict):
    """Process a map job asynchronously."""
    from app.core.metrics import worker_task_total, worker_task_duration_seconds, worker_active_tasks

    _start = _time_mod.monotonic()
    worker_active_tasks.labels(worker=_WORKER_NAME).inc()

    async def _do_map():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.map import MapRequest
        from app.services.mapper import map_website

        session_factory, db_engine = create_worker_session_factory()

        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            request = MapRequest(**config)

            # Cross-user cache check — skip the actual map if cached
            from app.core.cache import get_cached_map, set_cached_map
            cached = await get_cached_map(
                request.url, request.limit, request.include_subdomains,
                request.use_sitemap, request.search,
            )
            if cached:
                links_data = cached
                logger.info(f"Map cache hit for {request.url} ({len(links_data)} links)")
            else:
                links = await map_website(request)
                links_data = [link.model_dump() for link in links]
                # Cache for other users
                await set_cached_map(
                    request.url, request.limit, request.include_subdomains,
                    request.use_sitemap, request.search, links_data,
                )

            async with session_factory() as db:
                job_result = JobResult(
                    job_id=UUID(job_id),
                    url=request.url,
                    links=links_data,
                )
                db.add(job_result)

                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.total_pages = len(links_data)
                    job.completed_pages = len(links_data)
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            logger.error(f"Map job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()
        finally:
            await db_engine.dispose()

    try:
        _run_async(_do_map())
        worker_task_total.labels(worker=_WORKER_NAME, status="success").inc()
    except Exception:
        worker_task_total.labels(worker=_WORKER_NAME, status="failure").inc()
        raise
    finally:
        worker_active_tasks.labels(worker=_WORKER_NAME).dec()
        worker_task_duration_seconds.labels(worker=_WORKER_NAME).observe(
            _time_mod.monotonic() - _start
        )
