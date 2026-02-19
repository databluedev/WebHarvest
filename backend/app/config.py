from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WebHarvest"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-this-in-production"
    ENCRYPTION_KEY: str = "change-this-32-byte-key-in-prod!"  # Must be 32 bytes for AES-256
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    API_KEY_PREFIX: str = "wh_"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://webharvest:webharvest@localhost:5432/webharvest"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

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

    # Metrics
    METRICS_ENABLED: bool = True

    # Proxy
    USE_BUILTIN_PROXIES: bool = False

    # Batch Processing
    RATE_LIMIT_BATCH: int = 20
    MAX_BATCH_SIZE: int = 100

    # Search
    RATE_LIMIT_SEARCH: int = 30
    MAX_SEARCH_RESULTS: int = 10
    BRAVE_SEARCH_API_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
