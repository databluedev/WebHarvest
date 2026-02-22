"""Memory-adaptive concurrency control for crawl operations.

Monitors system memory usage and dynamically adjusts concurrency limits
to prevent OOM situations. Inspired by Crawl4AI's memory-aware dispatching.
"""
from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """Current memory statistics."""
    total_mb: float
    available_mb: float
    used_percent: float
    process_mb: float


def get_memory_stats() -> MemoryStats:
    """Get current system and process memory stats.
    
    Falls back to /proc/meminfo on Linux if psutil is not available.
    """
    try:
        import psutil
        vm = psutil.virtual_memory()
        proc = psutil.Process(os.getpid())
        return MemoryStats(
            total_mb=vm.total / (1024 * 1024),
            available_mb=vm.available / (1024 * 1024),
            used_percent=vm.percent,
            process_mb=proc.memory_info().rss / (1024 * 1024),
        )
    except ImportError:
        pass
    
    # Fallback: parse /proc/meminfo (Linux only)
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    meminfo[key] = int(parts[1])  # in kB
        
        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        total_mb = total_kb / 1024
        available_mb = available_kb / 1024
        used_percent = ((total_kb - available_kb) / total_kb * 100) if total_kb else 0
        
        # Process RSS from /proc/self/status
        proc_mb = 0.0
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        proc_mb = int(line.split()[1]) / 1024
                        break
        except Exception:
            pass
        
        return MemoryStats(
            total_mb=total_mb,
            available_mb=available_mb,
            used_percent=used_percent,
            process_mb=proc_mb,
        )
    except Exception:
        # Can't determine memory — return safe defaults
        return MemoryStats(
            total_mb=8192,
            available_mb=4096,
            used_percent=50.0,
            process_mb=0.0,
        )


class MemoryAdaptiveSemaphore:
    """Semaphore that adjusts its limit based on memory pressure.
    
    Periodically checks memory usage and:
    - Increases concurrency when memory is plentiful (< low_threshold)
    - Decreases concurrency when memory is tight (> high_threshold)
    - Hard-blocks when memory is critical (> critical_threshold)
    
    Args:
        base_limit: Starting concurrency limit
        min_limit: Minimum concurrency (never go below this)
        max_limit: Maximum concurrency (never exceed this)
        low_threshold: Memory usage % below which we can increase concurrency
        high_threshold: Memory usage % above which we decrease concurrency
        critical_threshold: Memory usage % above which we hard-block
        check_interval: Seconds between memory checks
    """
    
    def __init__(
        self,
        base_limit: int = 5,
        min_limit: int = 1,
        max_limit: int = 20,
        low_threshold: float = 50.0,
        high_threshold: float = 75.0,
        critical_threshold: float = 90.0,
        check_interval: float = 10.0,
    ):
        self._base_limit = base_limit
        self._min_limit = min_limit
        self._max_limit = max_limit
        self._low_threshold = low_threshold
        self._high_threshold = high_threshold
        self._critical_threshold = critical_threshold
        self._check_interval = check_interval
        
        self._current_limit = base_limit
        self._semaphore = asyncio.Semaphore(base_limit)
        self._active = 0
        self._lock = asyncio.Lock()
        self._monitor_task: asyncio.Task | None = None
        self._last_stats: MemoryStats | None = None
    
    @property
    def current_limit(self) -> int:
        return self._current_limit
    
    @property
    def active_count(self) -> int:
        return self._active
    
    @property
    def last_stats(self) -> MemoryStats | None:
        return self._last_stats
    
    async def start_monitoring(self) -> None:
        """Start the background memory monitoring task."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop the background memory monitoring task."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    async def _monitor_loop(self) -> None:
        """Periodically check memory and adjust limits."""
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                stats = get_memory_stats()
                self._last_stats = stats
                
                async with self._lock:
                    old_limit = self._current_limit
                    
                    if stats.used_percent >= self._critical_threshold:
                        # Critical: drop to minimum
                        self._current_limit = self._min_limit
                        if old_limit != self._min_limit:
                            logger.warning(
                                f"Memory critical ({stats.used_percent:.1f}%): "
                                f"concurrency {old_limit} → {self._min_limit}"
                            )
                    elif stats.used_percent >= self._high_threshold:
                        # High pressure: reduce by 1 (gradual)
                        new_limit = max(self._min_limit, self._current_limit - 1)
                        if new_limit != self._current_limit:
                            self._current_limit = new_limit
                            logger.info(
                                f"Memory high ({stats.used_percent:.1f}%): "
                                f"concurrency {old_limit} → {new_limit}"
                            )
                    elif stats.used_percent < self._low_threshold:
                        # Low pressure: increase by 1 (gradual)
                        new_limit = min(self._max_limit, self._current_limit + 1)
                        if new_limit != self._current_limit:
                            self._current_limit = new_limit
                            logger.debug(
                                f"Memory low ({stats.used_percent:.1f}%): "
                                f"concurrency {old_limit} → {new_limit}"
                            )
                    
                    # Rebuild semaphore if limit changed
                    if self._current_limit != old_limit:
                        # Create new semaphore with adjusted limit.
                        # Active tasks keep running; new acquisitions use new limit.
                        available = max(0, self._current_limit - self._active)
                        self._semaphore = asyncio.Semaphore(available)
                        
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Memory monitor error: {e}")
    
    async def acquire(self) -> None:
        """Acquire a slot, respecting memory-adjusted limits."""
        await self._semaphore.acquire()
        self._active += 1
    
    def release(self) -> None:
        """Release a slot."""
        self._active = max(0, self._active - 1)
        self._semaphore.release()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        self.release()
