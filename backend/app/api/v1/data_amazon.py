"""Amazon Data APIs.

Endpoints:
  POST /v1/data/amazon/products — Amazon product search results (structured JSON)
"""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.services.data_persistence import save_data_query
from app.schemas.data_amazon import (
    AmazonProductsRequest,
    AmazonProductsResponse,
)
from app.services.amazon_products import amazon_products

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/products",
    response_model=AmazonProductsResponse,
    response_model_exclude_none=True,
    summary="Amazon Product Search API",
    description=(
        "Search Amazon for products and return structured data including "
        "titles, prices, ratings, reviews, Prime eligibility, badges, and more. "
        "Supports pagination, sorting, price filters, and Prime-only filtering. "
        "Default domain is amazon.in; also supports .com, .co.uk, .de, etc. "
        "Results are cached for 5 minutes."
    ),
    response_description="Structured Amazon product search data",
)
async def search_amazon_products(
    request: AmazonProductsRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search Amazon and return structured product data."""
    # Rate limiting
    rl = await check_rate_limit_full(
        f"rate:data:{user.id}", settings.RATE_LIMIT_DATA_API
    )
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)
    if not rl.allowed:
        raise RateLimitError("Data API rate limit exceeded. Try again in a minute.")

    result = await amazon_products(
        query=request.query,
        num_results=request.num_results,
        page=request.page,
        domain=request.domain,
        sort_by=request.sort_by,
        min_price=request.min_price,
        max_price=request.max_price,
        prime_only=request.prime_only,
        language=request.language,
    )

    result_dict = result if isinstance(result, dict) else result.model_dump() if hasattr(result, "model_dump") else result.__dict__
    await save_data_query(
        db,
        user_id=user.id,
        platform="amazon",
        operation="products",
        query_params=request.model_dump(),
        result=result_dict,
        result_count=len(result_dict.get("products", [])),
        time_taken=result_dict.get("time_taken"),
        status="success" if result_dict.get("success") else "error",
        error_message=result_dict.get("error"),
    )

    return result
