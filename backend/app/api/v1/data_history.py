"""Data Query History API.

Endpoints for viewing, filtering, and managing saved Scrapper Pool queries.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.data_query import DataQuery
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/history",
    summary="List data query history",
    description="Paginated list of saved Scrapper Pool queries, filterable by platform and operation.",
)
async def list_data_queries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    platform: str | None = Query(None, description="Filter by platform (google, amazon)"),
    operation: str | None = Query(None, description="Filter by operation (search, shopping, maps, etc.)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List saved data queries for the current user."""
    query = select(DataQuery).where(DataQuery.user_id == user.id)

    if platform:
        query = query.where(DataQuery.platform == platform)
    if operation:
        query = query.where(DataQuery.operation == operation)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch (without full result payload for listing)
    query = query.order_by(desc(DataQuery.created_at)).offset(offset).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    items = []
    for r in rows:
        # Extract a short summary from query_params
        params = r.query_params or {}
        summary = params.get("query", "") or params.get("origin", "")
        if params.get("destination"):
            summary = f"{summary} → {params['destination']}"

        items.append({
            "id": str(r.id),
            "platform": r.platform,
            "operation": r.operation,
            "query_summary": summary,
            "result_count": r.result_count,
            "time_taken": r.time_taken,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "success": True,
        "queries": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/history/stats",
    summary="Data query statistics",
    description="Aggregate statistics for Scrapper Pool queries.",
)
async def data_query_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate stats for the user's data queries."""
    base = select(DataQuery).where(DataQuery.user_id == user.id)

    # Total count
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # By platform
    platform_rows = (
        await db.execute(
            select(DataQuery.platform, func.count())
            .where(DataQuery.user_id == user.id)
            .group_by(DataQuery.platform)
        )
    ).all()
    by_platform = {row[0]: row[1] for row in platform_rows}

    # By operation
    operation_rows = (
        await db.execute(
            select(DataQuery.operation, func.count())
            .where(DataQuery.user_id == user.id)
            .group_by(DataQuery.operation)
        )
    ).all()
    by_operation = {row[0]: row[1] for row in operation_rows}

    return {
        "success": True,
        "total_queries": total,
        "by_platform": by_platform,
        "by_operation": by_operation,
    }


@router.get(
    "/history/{query_id}",
    summary="Get data query detail",
    description="Retrieve a single saved data query with full results.",
)
async def get_data_query(
    query_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single data query with full result data."""
    record = await db.get(DataQuery, UUID(query_id))
    if not record or record.user_id != user.id:
        raise NotFoundError("Data query not found")

    return {
        "success": True,
        "query": {
            "id": str(record.id),
            "platform": record.platform,
            "operation": record.operation,
            "query_params": record.query_params,
            "result": record.result,
            "result_count": record.result_count,
            "time_taken": record.time_taken,
            "status": record.status,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        },
    }


@router.delete(
    "/history/{query_id}",
    summary="Delete a data query",
    description="Delete a saved data query and its results.",
)
async def delete_data_query(
    query_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved data query."""
    record = await db.get(DataQuery, UUID(query_id))
    if not record or record.user_id != user.id:
        raise NotFoundError("Data query not found")

    await db.delete(record)
    await db.flush()

    return {"success": True, "message": "Data query deleted"}
