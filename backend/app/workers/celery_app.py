from celery import Celery

from app.config import settings

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
        "app.workers.batch_worker.*": {"queue": "batch"},
        "app.workers.search_worker.*": {"queue": "search"},
        "app.workers.extract_worker.*": {"queue": "scrape"},
        "app.workers.monitor_worker.*": {"queue": "scrape"},
        "app.workers.schedule_worker.*": {"queue": "scrape"},  # Lightweight, reuse scrape queue
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
    },
)

# Explicitly include tasks
celery_app.conf.include = [
    "app.workers.scrape_worker",
    "app.workers.crawl_worker",
    "app.workers.map_worker",
    "app.workers.batch_worker",
    "app.workers.search_worker",
    "app.workers.schedule_worker",
    "app.workers.extract_worker",
    "app.workers.monitor_worker",
]
