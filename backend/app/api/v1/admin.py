"""Admin endpoints for Dead Letter Queue and system diagnostics."""

import json

from fastapi import APIRouter, Depends

from app.core.redis import redis_client
from app.api.deps import get_current_user
from app.workers.celery_app import DLQ_KEY

router = APIRouter()


@router.get(
    "/dlq",
    summary="List Dead Letter Queue entries",
    description="Returns tasks that failed after exhausting all retries. "
    "Useful for debugging persistent failures.",
    tags=["Admin"],
)
async def list_dlq(
    limit: int = 50,
    offset: int = 0,
    _user=Depends(get_current_user),
):
    """List DLQ entries with pagination."""
    entries_raw = await redis_client.lrange(DLQ_KEY, offset, offset + limit - 1)
    total = await redis_client.llen(DLQ_KEY)
    entries = []
    for raw in entries_raw:
        try:
            entries.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            entries.append({"raw": str(raw)})
    return {"total": total, "entries": entries}


@router.delete(
    "/dlq",
    summary="Purge all Dead Letter Queue entries",
    description="Permanently removes all entries from the DLQ.",
    tags=["Admin"],
)
async def purge_dlq(_user=Depends(get_current_user)):
    """Purge all DLQ entries."""
    deleted = await redis_client.delete(DLQ_KEY)
    return {"success": True, "deleted": deleted}


@router.post(
    "/dlq/{task_id}/retry",
    summary="Retry a DLQ task",
    description="Re-dispatches a failed task from the DLQ. The original task "
    "arguments are preserved.",
    tags=["Admin"],
)
async def retry_dlq_task(task_id: str, _user=Depends(get_current_user)):
    """Retry a specific DLQ entry by task_id."""
    entries_raw = await redis_client.lrange(DLQ_KEY, 0, -1)
    for i, raw in enumerate(entries_raw):
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if entry.get("task_id") == task_id:
            # Re-send the task
            from app.workers.celery_app import celery_app

            task_name = entry.get("task_name")
            args = entry.get("args", [])
            kwargs = entry.get("kwargs", {})
            celery_app.send_task(task_name, args=args, kwargs=kwargs)
            # Remove from DLQ
            await redis_client.lrem(DLQ_KEY, 1, raw)
            return {
                "success": True,
                "message": f"Task {task_id} re-dispatched",
                "task_name": task_name,
            }
    return {"success": False, "message": f"Task {task_id} not found in DLQ"}
