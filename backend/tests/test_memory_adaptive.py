"""Tests for memory-adaptive concurrency."""
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from app.services.memory_adaptive import (
    get_memory_stats,
    MemoryStats,
    MemoryAdaptiveSemaphore,
)


class TestMemoryStats:
    def test_returns_stats(self):
        stats = get_memory_stats()
        assert isinstance(stats, MemoryStats)
        assert stats.total_mb > 0
        assert 0 <= stats.used_percent <= 100


class TestMemoryAdaptiveSemaphore:
    @pytest.mark.asyncio
    async def test_basic_acquire_release(self):
        sem = MemoryAdaptiveSemaphore(base_limit=3)
        await sem.acquire()
        assert sem.active_count == 1
        sem.release()
        assert sem.active_count == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        sem = MemoryAdaptiveSemaphore(base_limit=3)
        async with sem:
            assert sem.active_count == 1
        assert sem.active_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        sem = MemoryAdaptiveSemaphore(base_limit=2)
        acquired = 0

        async def worker():
            nonlocal acquired
            async with sem:
                acquired += 1
                await asyncio.sleep(0.05)

        # Start 3 workers with limit of 2
        tasks = [asyncio.create_task(worker()) for _ in range(3)]
        await asyncio.sleep(0.01)  # Let first batch start
        assert sem.active_count <= 2
        await asyncio.gather(*tasks)
        assert acquired == 3

    @pytest.mark.asyncio
    async def test_properties(self):
        sem = MemoryAdaptiveSemaphore(base_limit=5, min_limit=1, max_limit=10)
        assert sem.current_limit == 5
        assert sem.active_count == 0
