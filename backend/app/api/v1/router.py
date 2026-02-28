from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    scrape,
    crawl,
    map,
    settings,
    proxy,
    search,
    usage,
    schedule,
    events,
    extract,
    monitor,
    webhook,
    jobs,
    data_amazon,
    data_google,
)

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["Crawl"])
api_router.include_router(map.router, prefix="/map", tags=["Map"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(proxy.router, prefix="/settings", tags=["Proxy"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(usage.router, prefix="/usage", tags=["Usage"])
api_router.include_router(schedule.router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(events.router, tags=["Events"])
api_router.include_router(extract.router, prefix="/extract", tags=["Extract"])
api_router.include_router(monitor.router, prefix="/monitors", tags=["Monitors"])
api_router.include_router(webhook.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(data_amazon.router, prefix="/data/amazon", tags=["Data: Amazon"])
api_router.include_router(data_google.router, prefix="/data/google", tags=["Data: Google"])
