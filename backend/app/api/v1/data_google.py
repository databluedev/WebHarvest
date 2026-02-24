"""Google Data APIs — Scrapper Pool.

Endpoints:
  POST /v1/data/google/search   — Google SERP results (structured JSON)
  POST /v1/data/google/shopping — Google Shopping with filters (structured JSON)
"""

import logging

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.schemas.data_google import (
    GoogleSearchRequest,
    GoogleSearchResponse,
    GoogleShoppingRequest,
    GoogleShoppingResponse,
)
from app.services.google_serp import google_search
from app.services.google_shopping import google_shopping

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/search",
    response_model=GoogleSearchResponse,
    response_model_exclude_none=True,
    summary="Google Search SERP API",
    description=(
        "Fetch structured Google search results including organic results, "
        "featured snippets, People Also Ask, related searches, and knowledge panels. "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Google SERP data",
)
async def search_google(
    request: GoogleSearchRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google and return structured SERP data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_search(
        query=request.query,
        num_results=request.num_results,
        page=request.page,
        language=request.language,
        country=request.country,
        safe_search=request.safe_search,
        time_range=request.time_range,
    )

    return result


@router.post(
    "/shopping",
    response_model=GoogleShoppingResponse,
    response_model_exclude_none=True,
    summary="Google Shopping API",
    description=(
        "Search Google Shopping with advanced filters — sort by price/rating, "
        "price range, condition (new/used), minimum rating, and free shipping. "
        "Returns structured product data with prices, merchants, ratings, and images. "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Google Shopping product data",
)
async def search_google_shopping(
    request: GoogleShoppingRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google Shopping with filters and return structured product data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_shopping(
        query=request.query,
        num_results=request.num_results,
        page=request.page,
        language=request.language,
        country=request.country,
        sort_by=request.sort_by,
        min_price=request.min_price,
        max_price=request.max_price,
        condition=request.condition,
        min_rating=request.min_rating,
        free_shipping=request.free_shipping,
    )

    return result
