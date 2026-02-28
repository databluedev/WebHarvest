"""Persistence helper for Scrapper Pool data queries.

Saves query results to the database so users can review them later.
All errors are caught and logged — persistence failures must never
break the API response.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_query import DataQuery

logger = logging.getLogger(__name__)


async def save_data_query(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform: str,
    operation: str,
    query_params: dict[str, Any],
    result: dict[str, Any],
    result_count: int = 0,
    time_taken: float | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> uuid.UUID | None:
    """Persist a data query result. Returns the new record's ID, or None on failure."""
    try:
        record = DataQuery(
            user_id=user_id,
            platform=platform,
            operation=operation,
            query_params=query_params,
            result=result,
            result_count=result_count,
            time_taken=time_taken,
            status=status,
            error_message=error_message,
        )
        db.add(record)
        await db.flush()
        return record.id
    except Exception:
        logger.exception("Failed to persist data query (platform=%s, operation=%s)", platform, operation)
        return None
