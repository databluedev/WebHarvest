import json
import logging
import traceback
from datetime import datetime, timezone

import redis
import sentry_sdk
from celery import Celery
from celery.signals import (
    task_failure, worker_shutting_down, after_setup_logger,
    after_setup_task_logger, celeryd_init,
)

from app.config import settings

# Initialize Sentry for Celery workers
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        environment=settings.SENTRY_ENVIRONMENT,
        release=f"webharvest@{settings.APP_VERSION}",
        send_default_pii=True,
        enable_logs=True,
        profile_session_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profile_lifecycle="trace",
    )

logger = logging.getLogger(__name__)

celery_app = Celery(
    "webharvest",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_priority=5,
    broker_transport_options={
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    },
    task_routes={
        "app.workers.scrape_worker.*": {"queue": "scrape"},
        "app.workers.crawl_worker.*": {"queue": "crawl"},
        "app.workers.map_worker.*": {"queue": "map"},
        "app.workers.search_worker.*": {"queue": "search"},
        "app.workers.extract_worker.*": {"queue": "scrape"},
        "app.workers.monitor_worker.*": {"queue": "scrape"},
        "app.workers.schedule_worker.*": {
            "queue": "scrape"
        },  # Lightweight, reuse scrape queue
        "app.workers.cleanup_worker.*": {"queue": "scrape"},
    },
    # Celery Beat schedule — periodic tasks
    beat_schedule={
        "check-schedules-every-60s": {
            "task": "app.workers.schedule_worker.check_schedules",
            "schedule": 60.0,  # Every 60 seconds
        },
        "check-monitors-every-60s": {
            "task": "app.workers.monitor_worker.check_monitors",
            "schedule": 60.0,  # Every 60 seconds
        },
        "cleanup-old-data-daily": {
            "task": "app.workers.cleanup_worker.cleanup_old_data",
            "schedule": 86400.0,  # Every 24 hours
        },
    },
    # Graceful shutdown
    worker_max_tasks_per_child=100,  # Prevent memory leaks
    worker_max_memory_per_child=512000,  # 512 MB soft limit
)

# Explicitly include tasks
celery_app.conf.include = [
    "app.workers.scrape_worker",
    "app.workers.crawl_worker",
    "app.workers.map_worker",
    "app.workers.search_worker",
    "app.workers.schedule_worker",
    "app.workers.extract_worker",
    "app.workers.monitor_worker",
    "app.workers.cleanup_worker",
]

# ---------------------------------------------------------------------------
# Dead Letter Queue — persist failed tasks after max retries
# ---------------------------------------------------------------------------

DLQ_KEY = "dlq:tasks"
DLQ_MAX_SIZE = 1000  # Keep at most 1000 entries


def _get_sync_redis():
    """Create a synchronous Redis client for signal handlers."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, args=None,
                    kwargs=None, traceback=None, einfo=None, **kw):
    """Push failed tasks (after max retries exhausted) to the DLQ."""
    # Only record if retries are exhausted
    retries = getattr(sender.request, "retries", 0) if sender else 0
    max_retries = getattr(sender, "max_retries", 0) if sender else 0
    if retries < max_retries:
        return  # Will be retried, not a final failure

    entry = {
        "task_id": task_id,
        "task_name": sender.name if sender else "unknown",
        "args": list(args) if args else [],
        "kwargs": dict(kwargs) if kwargs else {},
        "exception": str(exception),
        "traceback": str(einfo) if einfo else "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        r = _get_sync_redis()
        r.lpush(DLQ_KEY, json.dumps(entry))
        r.ltrim(DLQ_KEY, 0, DLQ_MAX_SIZE - 1)
        logger.warning(f"Task {task_id} ({sender.name if sender else '?'}) added to DLQ")
    except Exception as e:
        logger.error(f"Failed to write to DLQ: {e}")


# ---------------------------------------------------------------------------
# Graceful shutdown logging
# ---------------------------------------------------------------------------


class _PipeClosedFilter(logging.Filter):
    """Suppress Playwright's 'pipe closed by peer' warning spam."""
    def filter(self, record):
        return "pipe closed by peer" not in record.getMessage()


@after_setup_logger.connect
def _suppress_pipe_warnings(logger: logging.Logger, **kw):
    """Install pipe-closed filter on the Celery root logger."""
    logger.addFilter(_PipeClosedFilter())


@after_setup_task_logger.connect
def _suppress_pipe_warnings_task(logger: logging.Logger, **kw):
    """Install pipe-closed filter on the Celery task logger."""
    logger.addFilter(_PipeClosedFilter())


@worker_shutting_down.connect
def on_worker_shutting_down(sig=None, how=None, exitcode=None, **kw):
    """Log when a worker is shutting down."""
    logger.info(f"Worker shutting down (signal={sig}, how={how}, exitcode={exitcode})")


# ---------------------------------------------------------------------------
# Pre-warm browser pool — crawl workers only
# ---------------------------------------------------------------------------
#
# celeryd_init fires ONCE in the main worker process BEFORE forking children.
# We inspect the -Q queues CLI option to detect crawl workers and set a
# module-level flag that child processes inherit via fork (copy-on-write).
# worker_process_init then checks the flag before launching Chromium.
# ---------------------------------------------------------------------------
from celery.signals import worker_process_init  # noqa: E402

# Module-level flag set by celeryd_init, inherited by forked children via COW.
_is_crawl_worker = False


@celeryd_init.connect
def _detect_crawl_worker(conf=None, instance=None, options=None, **kwargs):
    """Set _is_crawl_worker flag based on -Q queues CLI option.

    Runs in the main (parent) process before prefork. The flag is inherited
    by all child processes via fork, so worker_process_init can check it.
    """
    global _is_crawl_worker
    raw_queues = (options or {}).get("queues") or []
    # Celery passes queues as a list (e.g. ['crawl'] or ['search', 'map']).
    # Handle both list and legacy comma-separated string formats.
    if isinstance(raw_queues, str):
        queue_list = [q.strip().lower() for q in raw_queues.split(",") if q.strip()]
    else:
        queue_list = [str(q).strip().lower() for q in raw_queues]
    _is_crawl_worker = "crawl" in queue_list
    queue_str = ",".join(queue_list) or "default"
    if _is_crawl_worker:
        logger.info(
            f"Crawl worker detected (queues={queue_str}), "
            "browser pre-warm enabled"
        )
    else:
        logger.info(
            f"Non-crawl worker (queues={queue_str}), "
            "browser pre-warm disabled"
        )


@worker_process_init.connect
def prewarm_browser_pool(sender=None, **kwargs):
    """Launch Chromium and create the persistent event loop on worker fork.

    Only runs in crawl workers (gated by _is_crawl_worker flag set in
    celeryd_init). The persistent loop is stored in crawl_worker._persistent_loop
    so that browser pool, HTTP clients, and cookie jar survive across tasks —
    eliminating re-initialization overhead between crawl jobs.
    """
    if not _is_crawl_worker:
        return

    import asyncio
    import os

    try:
        from app.services.browser import browser_pool
        import app.workers.crawl_worker as cw

        # Create the persistent loop and store it in crawl_worker
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(browser_pool.initialize())
        cw._persistent_loop = loop  # Tasks will reuse this loop
        logger.info("Pre-warmed BrowserPool + persistent loop on worker startup")
    except Exception as e:
        logger.warning(f"BrowserPool pre-warm failed (non-fatal): {e}")

    # Also ping stealth-engine to warm its browser pool
    try:
        import httpx

        stealth_url = os.environ.get(
            "STEALTH_ENGINE_URL", settings.STEALTH_ENGINE_URL
        )
        if stealth_url:
            resp = httpx.get(f"{stealth_url}/health", timeout=5.0)
            logger.info(f"Stealth-engine pre-warm: {resp.status_code}")
    except Exception:
        pass  # Stealth engine may not be available
