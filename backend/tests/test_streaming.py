"""Tests for NDJSON streaming."""
import asyncio
import json
import pytest
from app.services.streaming import ndjson_stream, serialize_result, StreamBuffer


async def _collect_stream(stream):
    """Helper to collect all bytes from an async iterator."""
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


class TestNDJSONStream:
    @pytest.mark.asyncio
    async def test_basic_stream(self):
        async def gen():
            yield {"url": "https://example.com", "status": 200}
            yield {"url": "https://example.com/page2", "status": 200}

        chunks = await _collect_stream(ndjson_stream(gen()))
        assert len(chunks) == 3  # 2 results + 1 completion

        # Last chunk should be completion
        last = json.loads(chunks[-1])
        assert last["status"] == "completed"

        # First two should be results
        first = json.loads(chunks[0])
        assert first["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        async def gen():
            return
            yield  # make it a generator

        chunks = await _collect_stream(ndjson_stream(gen()))
        assert len(chunks) == 1
        assert json.loads(chunks[0])["status"] == "completed"

    @pytest.mark.asyncio
    async def test_error_stream(self):
        async def gen():
            yield {"url": "https://example.com"}
            raise RuntimeError("Fetch failed")

        chunks = await _collect_stream(ndjson_stream(gen()))
        last = json.loads(chunks[-1])
        assert last["status"] == "error"
        assert "Fetch failed" in last["error"]


class TestSerializeResult:
    def test_full_result(self):
        data = {"url": "https://x.com", "markdown": "# Hi", "html": "<h1>Hi</h1>"}
        result = serialize_result(data)
        assert result == data

    def test_filtered_result(self):
        data = {"url": "https://x.com", "markdown": "# Hi", "html": "<h1>Hi</h1>"}
        result = serialize_result(data, include_fields=["url", "markdown"])
        assert "html" not in result
        assert result["url"] == "https://x.com"


class TestStreamBuffer:
    @pytest.mark.asyncio
    async def test_buffer_put_and_iterate(self):
        buf = StreamBuffer(max_buffer=10)
        await buf.put({"url": "a"})
        await buf.put({"url": "b"})
        await buf.finish()

        items = []
        async for item in buf:
            items.append(item)
        assert len(items) == 2
        assert items[0]["url"] == "a"
