import json
import logging
import traceback
from datetime import datetime, timezone

import redis
from celery import Celery
from celery.signals import task_failure, worker_shutting_down, after_setup_logger, after_setup_task_logger

from app.config import settings

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
