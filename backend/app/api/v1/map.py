import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import RateLimitError
from app.core.rate_limiter import check_rate_limit
from app.config import settings
from app.models.user import User
from app.schemas.map import MapRequest, MapResponse
from app.services.mapper import map_website

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=MapResponse)
async def map_site(
    request: MapRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Map all URLs on a website. Returns discovered URLs with titles and descriptions."""
    # Rate limiting
    allowed, _ = await check_rate_limit(
        f"rate:map:{user.id}", settings.RATE_LIMIT_MAP
    )
    if not allowed:
        raise RateLimitError("Map rate limit exceeded. Try again in a minute.")

    try:
        links = await map_website(request)
        return MapResponse(
            success=True,
            total=len(links),
            links=links,
        )
    except Exception as e:
        logger.error(f"Map failed for {request.url}: {e}")
        return MapResponse(
            success=False,
            total=0,
            links=[],
            error=str(e),
        )
