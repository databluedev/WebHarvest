from fastapi import APIRouter

from app.api.v1 import auth, scrape, crawl, map, settings, proxy, batch, search, usage, schedule, events, extract, monitor, webhook, jobs

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["Crawl"])
api_router.include_router(map.router, prefix="/map", tags=["Map"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(proxy.router, prefix="/settings", tags=["Proxy"])
api_router.include_router(batch.router, prefix="/batch", tags=["Batch"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(usage.router, prefix="/usage", tags=["Usage"])
api_router.include_router(schedule.router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(events.router, tags=["Events"])
api_router.include_router(extract.router, prefix="/extract", tags=["Extract"])
api_router.include_router(monitor.router, prefix="/monitors", tags=["Monitors"])
api_router.include_router(webhook.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
