"""DataBlue -- Python SDK for the DataBlue web scraping platform."""

__version__ = "0.1.0"

from webharvest.client import AsyncDataBlue, DataBlue
from webharvest.exceptions import (
    AuthenticationError,
    DataBlueError,
    JobFailedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
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
    "DataBlue",
    "AsyncDataBlue",
    # Exceptions
    "DataBlueError",
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
