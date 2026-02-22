import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
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

    # Capture IDs for the stream — the stream manages its own DB session
    # to avoid relying on the request-scoped session (which can close).
    _job_id = job.id
    _user_id = user.id

    async def event_stream():
        prev_status = None
        prev_completed = -1
        heartbeat_counter = 0

        while True:
            try:
                # Fresh session per iteration to avoid stale identity-map
                # reads — a long-lived session's get() returns cached ORM
                # state even after expire(), missing worker commits.
                async with async_session() as stream_db:
                    stream_job = await stream_db.get(Job, _job_id)
                    if not stream_job:
                        yield f"data: {json.dumps({'done': True, 'status': 'failed'})}\n\n"
                        return

                    status = stream_job.status
                    completed = stream_job.completed_pages or 0
                    total = stream_job.total_pages or 0

                if status != prev_status or completed != prev_completed:
                    data = json.dumps(
                        {
                            "status": status,
                            "completed_pages": completed,
                            "total_pages": total,
                        }
                    )
                    yield f"data: {data}\n\n"
                    prev_status = status
                    prev_completed = completed
                    heartbeat_counter = 0

                if status in ("completed", "failed", "cancelled"):
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

                # Heartbeat every ~15s (30 iterations * 0.5s) to keep
                # proxies and browsers from closing idle connections.
                heartbeat_counter += 1
                if heartbeat_counter >= 30:
                    yield ": heartbeat\n\n"
                    heartbeat_counter = 0

            except Exception as e:
                logger.warning(f"SSE stream error for {_job_id}: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
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
