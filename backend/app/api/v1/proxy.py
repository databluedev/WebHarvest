import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.proxy_config import ProxyConfig
from app.models.user import User
from app.schemas.proxy import (
    ProxyBulkCreateRequest,
    ProxyResponse,
    ProxyListResponse,
)
from app.services.proxy import ProxyManager

router = APIRouter()
logger = logging.getLogger(__name__)


def _mask_and_respond(config: ProxyConfig) -> ProxyResponse:
    return ProxyResponse(
        id=config.id,
        proxy_url_masked=ProxyManager.mask_url(config.proxy_url),
        proxy_type=config.proxy_type,
        label=config.label,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.post("/proxies", response_model=ProxyListResponse)
async def add_proxies(
    request: ProxyBulkCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add one or more proxies (bulk). Each line is a proxy URL."""
    added = []
    for proxy_url in request.proxies:
        proxy_url = proxy_url.strip()
        if not proxy_url:
            continue
        config = ProxyConfig(
            user_id=user.id,
            proxy_url=proxy_url,
            proxy_type=request.proxy_type,
        )
        db.add(config)
        added.append(config)

    await db.flush()

    return ProxyListResponse(
        proxies=[_mask_and_respond(c) for c in added],
        total=len(added),
    )


@router.get("/proxies", response_model=ProxyListResponse)
async def list_proxies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all proxies for the current user."""
    result = await db.execute(
        select(ProxyConfig)
        .where(ProxyConfig.user_id == user.id)
        .order_by(ProxyConfig.created_at.desc())
    )
    configs = result.scalars().all()

    return ProxyListResponse(
        proxies=[_mask_and_respond(c) for c in configs],
        total=len(configs),
    )


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a proxy configuration."""
    config = await db.get(ProxyConfig, UUID(proxy_id))
    if not config or config.user_id != user.id:
        raise NotFoundError("Proxy not found")

    await db.delete(config)
    return {"success": True, "message": "Proxy deleted"}
