import logging
import secrets

from pydantic_settings import BaseSettings
from typing import List

_logger = logging.getLogger(__name__)


def _generate_secret(name: str) -> str:
    """Generate a random secret and warn that it should be set explicitly."""
    value = secrets.token_urlsafe(48)
    _logger.warning(
        "%s not set — using auto-generated value. "
        "Set %s in your .env or environment for production.",
        name,
        name,
    )
    return value


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WebHarvest"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Security — auto-generate if not provided (with startup warning)
    SECRET_KEY: str = ""
    ENCRYPTION_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    API_KEY_PREFIX: str = "wh_"

    # Database — defaults to SQLite so `docker compose up` works without .env
    DATABASE_URL: str = "sqlite+aiosqlite:///./webharvest.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    def model_post_init(self, __context) -> None:
        if not self.SECRET_KEY or self.SECRET_KEY == "change-this-in-production":
            object.__setattr__(self, "SECRET_KEY", _generate_secret("SECRET_KEY"))
        if (
            not self.ENCRYPTION_KEY
            or self.ENCRYPTION_KEY == "change-this-32-byte-key-in-prod!"
        ):
            # Must be exactly 32 bytes for AES-256
            key = secrets.token_urlsafe(24)[:32]
            _logger.warning(
                "ENCRYPTION_KEY not set — using auto-generated value. "
                "Set ENCRYPTION_KEY in your .env or environment for production.",
            )
            object.__setattr__(self, "ENCRYPTION_KEY", key)

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Browser Pool
    BROWSER_POOL_SIZE: int = 8
    BROWSER_HEADLESS: bool = True
    CHROMIUM_POOL_SIZE: int = 6
    FIREFOX_POOL_SIZE: int = 2

    # Rate Limiting (per minute)
    RATE_LIMIT_SCRAPE: int = 100
    RATE_LIMIT_CRAWL: int = 20
    RATE_LIMIT_MAP: int = 50

    # Scraping
    DEFAULT_TIMEOUT: int = 30000  # ms
    DEFAULT_WAIT_FOR: int = 0  # ms
    MAX_CRAWL_PAGES: int = 1000
    MAX_CRAWL_DEPTH: int = 10
    MAX_CONCURRENT_SCRAPES: int = (
        5  # Per-worker API concurrency (4 workers × 5 = 20 max)
    )
    SCRAPE_API_TIMEOUT: int = 90  # Max seconds for a single scrape API call

    # Database Pool
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    WORKER_DB_POOL_SIZE: int = 5

    # Redis Pool
    REDIS_MAX_CONNECTIONS: int = 50

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    STRATEGY_CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Go HTML-to-Markdown sidecar (empty = disabled, fallback to Python markdownify)
    GO_HTML_TO_MD_URL: str = ""

    # Stealth Engine sidecar (empty = disabled, fallback to local browser_pool)
    STEALTH_ENGINE_URL: str = ""

    # Sentry
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.2
    SENTRY_ENVIRONMENT: str = "development"

    # Logging
    LOG_FORMAT: str = "json"  # "json" for production, "text" for development
    LOG_LEVEL: str = "INFO"

    # Metrics
    METRICS_ENABLED: bool = True

    # Proxy
    USE_BUILTIN_PROXIES: bool = False
    SCRAPE_DO_API_KEY: str = ""  # scrape.do proxy API key — auto-used for hard sites

    # Search
    RATE_LIMIT_SEARCH: int = 30
    MAX_SEARCH_RESULTS: int = 10
    BRAVE_SEARCH_API_KEY: str = ""
    SEARXNG_URL: str = ""  # Self-hosted SearXNG instance (empty = disabled)

    # Data Retention
    DATA_RETENTION_DAYS: int = 30
    MONITOR_CHECK_RETENTION_DAYS: int = 90

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
