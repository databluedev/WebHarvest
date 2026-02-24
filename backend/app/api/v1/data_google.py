"""Google Data APIs — Scrapper Pool.

Endpoints:
  POST /v1/data/google/search — Google SERP results (structured JSON)
"""

import logging

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.schemas.data_google import GoogleSearchRequest, GoogleSearchResponse
from app.services.google_serp import google_search

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
