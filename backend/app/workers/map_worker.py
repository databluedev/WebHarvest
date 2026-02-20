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


@celery_app.task(name="app.workers.map_worker.process_map", bind=True, max_retries=2)
def process_map(self, job_id: str, config: dict):
    """Process a map job asynchronously."""

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
            links = await map_website(request)

            async with session_factory() as db:
                # Store results
                for link in links:
                    job_result = JobResult(
                        job_id=UUID(job_id),
                        url=link.url,
                        metadata_={
                            "title": link.title,
                            "description": link.description,
                        },
                    )
                    db.add(job_result)

                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.total_pages = len(links)
                    job.completed_pages = len(links)
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

    _run_async(_do_map())
