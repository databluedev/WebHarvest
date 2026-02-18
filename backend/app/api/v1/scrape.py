import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.core.rate_limiter import check_rate_limit
from app.core.metrics import scrape_requests_total
from app.config import settings
from app.models.user import User
from app.schemas.scrape import ScrapeRequest, ScrapeResponse
from app.services.scraper import scrape_url
from app.services.llm_extract import extract_with_llm

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ScrapeResponse)
async def scrape(
    request: ScrapeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scrape a single URL and return content in requested formats."""
    # Rate limiting
    allowed, remaining = await check_rate_limit(
        f"rate:scrape:{user.id}", settings.RATE_LIMIT_SCRAPE
    )
    if not allowed:
        from app.core.exceptions import RateLimitError
        raise RateLimitError("Scrape rate limit exceeded. Try again in a minute.")

    try:
        # Load proxy manager if use_proxy is set
        proxy_manager = None
        if getattr(request, "use_proxy", False):
            from app.services.proxy import ProxyManager
            proxy_manager = await ProxyManager.from_user(db, user.id)

        # Scrape the URL
        result = await scrape_url(request, proxy_manager=proxy_manager)

        # LLM extraction if requested
        if request.extract and result.markdown:
            extract_result = await extract_with_llm(
                db=db,
                user_id=user.id,
                content=result.markdown,
                prompt=request.extract.prompt,
                schema=request.extract.schema_,
            )
            result.extract = extract_result

        scrape_requests_total.labels(status="success").inc()
        return ScrapeResponse(success=True, data=result)

    except BadRequestError:
        raise
    except Exception as e:
        logger.error(f"Scrape failed for {request.url}: {e}")
        scrape_requests_total.labels(status="error").inc()
        return ScrapeResponse(success=False, error=str(e))
