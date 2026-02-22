"""NDJSON streaming support for crawl and scrape results."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


async def ndjson_stream(results: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    """Convert an async iterator of dicts to NDJSON bytes.

    Each dict is serialized as a JSON line followed by newline.
    Ends with a status line: {"status": "completed"}.
    """
    try:
        async for result in results:
            line = json.dumps(result, default=str, ensure_ascii=False)
            yield (line + "\n").encode("utf-8")
    except Exception as e:
        error_line = json.dumps({"status": "error", "error": str(e)}, default=str)
        yield (error_line + "\n").encode("utf-8")
        return

    done_line = json.dumps({"status": "completed"})
    yield (done_line + "\n").encode("utf-8")


def serialize_result(data: dict, include_fields: list[str] | None = None) -> dict:
    """Serialize a crawl/scrape result for streaming.

    Optionally filter to only include specified fields.
    """
    if include_fields:
        return {k: v for k, v in data.items() if k in include_fields}
    return data


class StreamBuffer:
    """Buffer for accumulating streaming results with backpressure."""

    def __init__(self, max_buffer: int = 100):
        import asyncio
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=max_buffer)
        self._done = False

    async def put(self, item: dict) -> None:
        """Add a result to the stream buffer."""
        await self._queue.put(item)

    async def finish(self) -> None:
        """Signal that no more results will be added."""
        self._done = True
        await self._queue.put(None)

    async def __aiter__(self) -> AsyncIterator[dict]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item
