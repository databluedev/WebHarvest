import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import decode_access_token
from app.models.job import Job
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_user_from_token(token: str, db: AsyncSession) -> User:
    """Authenticate via query-param token (needed for EventSource which can't set headers)."""
    if not token:
        raise AuthenticationError("Missing token")

    if token.startswith("wh_"):
        from app.services.auth import get_user_by_api_key
        user = await get_user_by_api_key(db, token)
        if not user:
            raise AuthenticationError("Invalid API key")
        return user

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AuthenticationError("Invalid or expired token")

    result = await db.execute(select(User).where(User.id == UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found")
    return user


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — streams job status updates until completion.

    Uses query-param token auth since EventSource API can't set headers.
    """
    user = await _get_user_from_token(token, db)

    job = await db.get(Job, UUID(job_id))
    if not job or job.user_id != user.id:
        raise NotFoundError("Job not found")

    async def event_stream():
        prev_status = None
        prev_completed = -1

        while True:
            await db.refresh(job)

            status = job.status
            completed = job.completed_pages or 0

            if status != prev_status or completed != prev_completed:
                data = json.dumps({
                    "status": status,
                    "completed_pages": completed,
                    "total_pages": job.total_pages or 0,
                })
                yield f"data: {data}\n\n"
                prev_status = status
                prev_completed = completed

            if status in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
