import logging

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import settings
from app.core.metrics import get_metrics, get_metrics_content_type

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    summary="Liveness check",
    description="Basic liveness probe that returns HTTP 200 if the application process is running. Suitable for Kubernetes liveness probes or load balancer health checks.",
)
async def liveness():
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "healthy"}


@router.get(
    "/health/ready",
    summary="Readiness check",
    description="Readiness probe that verifies connectivity to the database, Redis, and the browser pool. Returns HTTP 200 with individual check statuses when all dependencies are healthy, or HTTP 503 if any dependency is unavailable.",
)
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


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Expose application metrics in Prometheus exposition format. Returns HTTP 404 if metrics collection is disabled in the application configuration.",
)
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.METRICS_ENABLED:
        return Response(content="Metrics disabled", status_code=404)

    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )
