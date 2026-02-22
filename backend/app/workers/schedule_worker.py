"""Periodic Celery Beat task to check and trigger due schedules."""

import asyncio
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
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


@celery_app.task(name="app.workers.schedule_worker.check_schedules")
def check_schedules():
    """Check all active schedules and trigger any that are due."""

    async def _check():
        from croniter import croniter
        from sqlalchemy import select

        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.schedule import Schedule

        session_factory, db_engine = create_worker_session_factory()

        try:
            now = datetime.now(timezone.utc)

            async with session_factory() as db:
                # Find all active schedules where next_run_at <= now
                result = await db.execute(
                    select(Schedule).where(
                        Schedule.is_active == True,  # noqa: E712
                        Schedule.next_run_at <= now,
                    )
                )
                due_schedules = result.scalars().all()

                if not due_schedules:
                    return

                logger.info(f"Found {len(due_schedules)} due schedule(s)")

                for schedule in due_schedules:
                    try:
                        # Create a job from the schedule config
                        config = dict(schedule.config)
                        config["schedule_id"] = str(schedule.id)

                        # Add webhook if set on schedule
                        if schedule.webhook_url:
                            config["webhook_url"] = schedule.webhook_url

                        job = Job(
                            user_id=schedule.user_id,
                            type=schedule.schedule_type,
                            status="pending",
                            config=config,
                        )
                        db.add(job)
                        await db.flush()

                        # Dispatch to the appropriate worker
                        if schedule.schedule_type == "crawl":
                            from app.workers.crawl_worker import process_crawl

                            process_crawl.delay(str(job.id), config)
                        elif schedule.schedule_type == "scrape":
                            from app.workers.scrape_worker import process_scrape

                            process_scrape.delay(str(job.id), config)

                        # Update schedule
                        schedule.last_run_at = now
                        schedule.run_count += 1

                        # Compute next run
                        cron = croniter(schedule.cron_expression, now)
                        schedule.next_run_at = cron.get_next(datetime).replace(
                            tzinfo=timezone.utc
                        )

                        logger.info(
                            f"Triggered schedule '{schedule.name}' "
                            f"(id={schedule.id}), job={job.id}, "
                            f"next_run={schedule.next_run_at}"
                        )

                    except Exception as e:
                        logger.error(f"Failed to trigger schedule {schedule.id}: {e}")

                await db.commit()

        except Exception as e:
            logger.error(f"check_schedules failed: {e}")
        finally:
            await db_engine.dispose()

    _run_async(_check())
