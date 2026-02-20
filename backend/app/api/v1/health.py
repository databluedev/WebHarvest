import logging

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import settings
from app.core.metrics import get_metrics, get_metrics_content_type

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def liveness():
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — checks DB, Redis, and browser pool connectivity."""
    checks = {}

    # Check database
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Check Redis
    try:
        from app.core.redis import redis_client

        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Check browser pool
    try:
        from app.services.browser import browser_pool

        if browser_pool._initialized:
            checks["browser_pool"] = "ok"
        else:
            checks["browser_pool"] = "not initialized"
    except Exception as e:
        checks["browser_pool"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return Response(
        content=__import__("json").dumps(
            {"status": "ready" if all_ok else "not ready", "checks": checks}
        ),
        status_code=status_code,
        media_type="application/json",
    )


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.METRICS_ENABLED:
        return Response(content="Metrics disabled", status_code=404)

    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )
