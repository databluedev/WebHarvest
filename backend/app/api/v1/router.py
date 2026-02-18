from fastapi import APIRouter

from app.api.v1 import auth, scrape, crawl, map, settings, proxy, batch, search

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["Crawl"])
api_router.include_router(map.router, prefix="/map", tags=["Map"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(proxy.router, prefix="/settings", tags=["Proxy"])
api_router.include_router(batch.router, prefix="/batch", tags=["Batch"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
