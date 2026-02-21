"""WebHarvest -- Python SDK for the WebHarvest web scraping platform."""

__version__ = "0.1.0"

from webharvest.client import AsyncWebHarvest, WebHarvest
from webharvest.exceptions import (
    AuthenticationError,
    JobFailedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    WebHarvestError,
)
from webharvest.models import (
    CrawlJob,
    CrawlPageData,
    CrawlStatus,
    DayCount,
    JobHistoryItem,
    LinkResult,
    MapResult,
    PageData,
    PageMetadata,
    Schedule,
    ScheduleList,
    ScheduleRuns,
    ScheduleTrigger,
    ScrapeResult,
    SearchJob,
    SearchResultItem,
    SearchStatus,
    TokenResponse,
    TopDomains,
    UsageHistory,
    UsageStats,
    UserInfo,
)

__all__ = [
    # Version
    "__version__",
    # Clients
    "WebHarvest",
    "AsyncWebHarvest",
    # Exceptions
    "WebHarvestError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "JobFailedError",
    "TimeoutError",
    # Models
    "CrawlJob",
    "CrawlPageData",
    "CrawlStatus",
    "DayCount",
    "JobHistoryItem",
    "LinkResult",
    "MapResult",
    "PageData",
    "PageMetadata",
    "Schedule",
    "ScheduleList",
    "ScheduleRuns",
    "ScheduleTrigger",
    "ScrapeResult",
    "SearchJob",
    "SearchResultItem",
    "SearchStatus",
    "TokenResponse",
    "TopDomains",
    "UsageHistory",
    "UsageStats",
    "UserInfo",
]
