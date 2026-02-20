from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ---------------------------------------------------------------------------
# Existing counters (scrape/crawl/batch/search job totals)
# ---------------------------------------------------------------------------
scrape_requests_total = Counter(
    "scrape_requests_total",
    "Total number of scrape requests",
    ["status"],
)
crawl_jobs_total = Counter(
    "crawl_jobs_total",
    "Total number of crawl jobs started",
    ["status"],
)
batch_jobs_total = Counter(
    "batch_jobs_total",
    "Total number of batch jobs started",
    ["status"],
)
search_jobs_total = Counter(
    "search_jobs_total",
    "Total number of search jobs started",
    ["status"],
)

# ---------------------------------------------------------------------------
# Worker task metrics
# ---------------------------------------------------------------------------
worker_task_total = Counter(
    "worker_task_total",
    "Total worker tasks by worker name and outcome",
    ["worker", "status"],
)
worker_task_duration_seconds = Histogram(
    "worker_task_duration_seconds",
    "Duration of worker tasks in seconds",
    ["worker"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
)
worker_active_tasks = Gauge(
    "worker_active_tasks",
    "Number of currently active worker tasks",
    ["worker"],
)

# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests to the API",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ---------------------------------------------------------------------------
# Existing histograms
# ---------------------------------------------------------------------------
scrape_duration_seconds = Histogram(
    "scrape_duration_seconds",
    "Time spent scraping a single URL",
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)
crawl_page_duration_seconds = Histogram(
    "crawl_page_duration_seconds",
    "Time spent scraping a single page during crawl",
    buckets=[0.5, 1, 2, 5, 10, 30],
)

# ---------------------------------------------------------------------------
# Existing gauges
# ---------------------------------------------------------------------------
active_browser_contexts = Gauge(
    "active_browser_contexts",
    "Number of currently active browser contexts",
)
db_pool_size = Gauge(
    "db_pool_size",
    "Current database connection pool size",
)

# ---------------------------------------------------------------------------
# Infrastructure gauges
# ---------------------------------------------------------------------------
circuit_breaker_open_total = Gauge(
    "circuit_breaker_open_total",
    "Number of domains with open circuit breakers",
)
redis_connection_status = Gauge(
    "redis_connection_status",
    "Redis connection status (1=connected, 0=disconnected)",
)
browser_pool_exhausted_total = Counter(
    "browser_pool_exhausted_total",
    "Number of times the browser pool was exhausted",
)
dlq_entries_total = Counter(
    "dlq_entries_total",
    "Total number of tasks added to the Dead Letter Queue",
)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
