"""Google Data APIs — Scrapper Pool.

Endpoints:
  POST /v1/data/google/search   — Google SERP results (structured JSON)
  POST /v1/data/google/shopping — Google Shopping with filters (structured JSON)
  POST /v1/data/google/maps     — Google Maps places and details (structured JSON)
"""

import logging

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import BadRequestError, RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.schemas.data_google import (
    GoogleMapsRequest,
    GoogleMapsResponse,
    GoogleSearchRequest,
    GoogleSearchResponse,
    GoogleShoppingRequest,
    GoogleShoppingResponse,
)
from app.services.google_maps import google_maps
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
        "Search Google Shopping with filters — sort by price/rating/reviews, "
        "minimum rating, and country targeting. "
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
        min_rating=request.min_rating,
    )

    return result


@router.post(
    "/maps",
    response_model=GoogleMapsResponse,
    response_model_exclude_none=True,
    summary="Google Maps API",
    description=(
        "Search Google Maps for places or get detailed info for a single location. "
        "Supports search by query + coordinates, nearby search, and place details "
        "by Place ID, CID/Ludocid, or data parameter. "
        "Includes ratings, reviews, hours, contact info, attributes, and more. "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Google Maps place data",
)
async def search_google_maps(
    request: GoogleMapsRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google Maps or get place details."""
    # Validate: at least one search/detail parameter is required
    if not any([request.query, request.coordinates, request.place_id, request.cid, request.data]):
        raise BadRequestError(
            "At least one of query, coordinates, place_id, cid, or data is required."
        )

    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_maps(
        query=request.query,
        coordinates=request.coordinates,
        radius=request.radius,
        zoom=request.zoom,
        type_filter=request.type,
        keyword=request.keyword,
        min_rating=request.min_rating,
        open_now=request.open_now,
        price_level=request.price_level,
        sort_by=request.sort_by,
        num_results=request.num_results,
        place_id=request.place_id,
        cid=request.cid,
        data=request.data,
        language=request.language,
        country=request.country,
        include_reviews=request.include_reviews,
        reviews_limit=request.reviews_limit,
        reviews_sort=request.reviews_sort,
    )

    return result
