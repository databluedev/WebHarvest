from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Counters
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

# Histograms
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

# Gauges
active_browser_contexts = Gauge(
    "active_browser_contexts",
    "Number of currently active browser contexts",
)
db_pool_size = Gauge(
    "db_pool_size",
    "Current database connection pool size",
)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
