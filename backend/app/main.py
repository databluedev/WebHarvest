import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pythonjsonlogger.json import JsonFormatter

from app.api.v1.router import api_router
from app.api.v1.health import router as health_router
from app.config import settings
from app.services.browser import browser_pool

# Structured JSON logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter(
    fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    rename_fields={"levelname": "level", "name": "logger", "asctime": "timestamp"},
))
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup — browsers are lazy-initialized on first scrape request
    # to avoid spawning 8 browser processes across 4 Uvicorn workers
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await browser_pool.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="WebHarvest - Open source web crawling platform that outperforms Firecrawl. "
    "Scrape, crawl, and map websites with AI-powered extraction. "
    "Bring Your Own Key (BYOK) for LLM processing.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Gzip compression — 50-70% bandwidth savings on JSON/HTML responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Health & metrics routes (no /v1 prefix)
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "running",
    }
