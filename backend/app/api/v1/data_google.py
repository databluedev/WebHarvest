"""Google Data APIs — Scrapper Pool.

Endpoints:
  POST /v1/data/google/search   — Google SERP results (structured JSON)
  POST /v1/data/google/shopping — Google Shopping with filters (structured JSON)
  POST /v1/data/google/maps     — Google Maps places and details (structured JSON)
  POST /v1/data/google/news     — Google News articles (structured JSON)
  POST /v1/data/google/jobs     — Google Careers job listings (structured JSON)
  POST /v1/data/google/images   — Google Images with filters (structured JSON)
  POST /v1/data/google/flights  — Google Flights search (structured JSON)
"""

import logging

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import BadRequestError, RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.schemas.data_google import (
    GoogleFlightsRequest,
    GoogleFlightsResponse,
    GoogleImagesRequest,
    GoogleImagesResponse,
    GoogleJobsRequest,
    GoogleJobsResponse,
    GoogleMapsRequest,
    GoogleMapsResponse,
    GoogleNewsRequest,
    GoogleNewsResponse,
    GoogleSearchRequest,
    GoogleSearchResponse,
    GoogleShoppingRequest,
    GoogleShoppingResponse,
)
from app.services.google_flights import google_flights
from app.services.google_images import google_images
from app.services.google_jobs import google_jobs
from app.services.google_maps import google_maps
from app.services.google_news import google_news
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


@router.post(
    "/news",
    response_model=GoogleNewsResponse,
    response_model_exclude_none=True,
    summary="Google News API",
    description=(
        "Search Google News and return structured article data including titles, "
        "sources, dates, snippets, and thumbnails. "
        "Supports time range filtering and sorting by date or relevance. "
        "No result limit — fetches as many articles as available (up to 500). "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Google News article data",
)
async def search_google_news(
    request: GoogleNewsRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google News and return structured article data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_news(
        query=request.query,
        num_results=request.num_results,
        language=request.language,
        country=request.country,
        time_range=request.time_range,
        sort_by=request.sort_by,
    )

    return result


@router.post(
    "/jobs",
    response_model=GoogleJobsResponse,
    response_model_exclude_none=True,
    summary="Google Jobs (Careers) API",
    description=(
        "Search Google Careers for job listings with structured data including "
        "titles, locations, descriptions, qualifications, experience levels, and more. "
        "Supports all Google Careers filters: remote, experience level, employment type, "
        "organization, location, degree, and skills. "
        "20 results per page with pagination. Results are cached for 5 minutes."
    ),
    response_description="Structured Google Careers job listing data",
)
async def search_google_jobs(
    request: GoogleJobsRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google Careers and return structured job listing data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_jobs(
        query=request.query,
        num_results=request.num_results,
        has_remote=request.has_remote,
        target_level=request.target_level,
        employment_type=request.employment_type,
        company=request.company,
        location=request.location,
        degree=request.degree,
        skills=request.skills,
        sort_by=request.sort_by,
    )

    return result


@router.post(
    "/images",
    response_model=GoogleImagesResponse,
    response_model_exclude_none=True,
    summary="Google Images API",
    description=(
        "Search Google Images and return structured image data including "
        "full-resolution URLs, dimensions, thumbnails, source pages, domains, "
        "file sizes, and dominant colours. "
        "Supports filters: colour, size, type, time range, aspect ratio, and licence. "
        "No result limit — set num_results=0 to fetch all pages until exhausted (~500-600 images). "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Google Images data",
)
async def search_google_images(
    request: GoogleImagesRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google Images and return structured image data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_images(
        query=request.query,
        num_results=request.num_results,
        language=request.language,
        country=request.country,
        safe_search=request.safe_search,
        colour=request.colour,
        size=request.size,
        type_filter=request.type,
        time_range=request.time_range,
        aspect_ratio=request.aspect_ratio,
        licence=request.licence,
    )

    return result


@router.post(
    "/flights",
    response_model=GoogleFlightsResponse,
    response_model_exclude_none=True,
    summary="Google Flights API",
    description=(
        "Search Google Flights for flight listings with pricing, schedules, "
        "airlines, stops, and duration. Uses reverse-engineered protobuf encoding "
        "to build the search URL — HTTP-only, no browser needed. "
        "Supports round-trip and one-way searches, cabin class, passenger counts, "
        "and max stops filter. Results are cached for 5 minutes."
    ),
    response_description="Structured Google Flights data",
)
async def search_google_flights(
    request: GoogleFlightsRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    """Search Google Flights and return structured flight data."""
    # Validate passenger count
    total_pax = request.adults + request.children + request.infants_in_seat + request.infants_on_lap
    if total_pax > 9:
        raise BadRequestError("Total passengers cannot exceed 9.")
    if request.infants_on_lap > request.adults:
        raise BadRequestError("Each lap infant requires at least one adult.")

    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await google_flights(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.departure_date,
        return_date=request.return_date,
        adults=request.adults,
        children=request.children,
        infants_in_seat=request.infants_in_seat,
        infants_on_lap=request.infants_on_lap,
        seat=request.seat,
        max_stops=request.max_stops,
        language=request.language,
        currency=request.currency,
        country=request.country,
    )

    return result
