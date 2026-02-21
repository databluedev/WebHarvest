import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
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


@celery_app.task(name="app.workers.cleanup_worker.cleanup_old_data", bind=True)
def cleanup_old_data(self):
    """Delete old jobs, webhook deliveries, and monitor checks based on retention settings."""

    async def _do_cleanup():
        from sqlalchemy import delete, select

        from app.config import settings
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.models.webhook_delivery import WebhookDelivery
        from app.models.monitor import MonitorCheck

        session_factory, db_engine = create_worker_session_factory()

        job_cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.DATA_RETENTION_DAYS
        )
        webhook_cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.DATA_RETENTION_DAYS
        )
        monitor_cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.MONITOR_CHECK_RETENTION_DAYS
        )

        try:
            async with session_factory() as db:
                # Delete old job results first (FK constraint)
                old_jobs = await db.execute(
                    select(Job.id).where(Job.created_at < job_cutoff)
                )
                old_job_ids = [row[0] for row in old_jobs.fetchall()]

                if old_job_ids:
                    await db.execute(
                        delete(JobResult).where(JobResult.job_id.in_(old_job_ids))
                    )
                    await db.execute(delete(Job).where(Job.id.in_(old_job_ids)))
                    logger.info(
                        f"Cleaned up {len(old_job_ids)} old jobs and their results"
                    )

                # Delete old webhook deliveries
                result = await db.execute(
                    delete(WebhookDelivery).where(
                        WebhookDelivery.created_at < webhook_cutoff
                    )
                )
                webhook_count = result.rowcount
                if webhook_count:
                    logger.info(f"Cleaned up {webhook_count} old webhook deliveries")

                # Delete old monitor checks
                result = await db.execute(
                    delete(MonitorCheck).where(MonitorCheck.checked_at < monitor_cutoff)
                )
                check_count = result.rowcount
                if check_count:
                    logger.info(f"Cleaned up {check_count} old monitor checks")

                await db.commit()

        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
        finally:
            await db_engine.dispose()

    _run_async(_do_cleanup())
