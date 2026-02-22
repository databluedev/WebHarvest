"""Hook system for crawler lifecycle customization.

Hooks are async callables that execute at specific points in the crawl
lifecycle. They can modify page state, add headers, handle auth, etc.

Supported hook points:
- on_browser_created: (browser) -> called after browser launch
- before_goto: (page, url) -> called before navigating to URL
- after_goto: (page, url, response) -> called after page loads
- before_extract: (page, html) -> called before content extraction
- after_extract: (page, result) -> called after extraction
- on_error: (page, url, error) -> called on scrape error
- before_return: (result) -> called before returning result
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Valid hook points
HOOK_POINTS = frozenset({
    "on_browser_created",
    "before_goto",
    "after_goto",
    "before_extract",
    "after_extract",
    "on_error",
    "before_return",
})


class HookManager:
    """Manages and executes lifecycle hooks."""

    def __init__(self, timeout: float = 30.0):
        self._hooks: dict[str, list[Callable[..., Awaitable]]] = {
            point: [] for point in HOOK_POINTS
        }
        self._timeout = timeout
        self._execution_log: list[dict] = []
        self._errors: dict[str, list[str]] = {}

    def register(self, hook_point: str, callback: Callable[..., Awaitable]) -> None:
        """Register a hook callback for a specific point."""
        if hook_point not in HOOK_POINTS:
            raise ValueError(
                f"Invalid hook point: {hook_point}. "
                f"Valid: {', '.join(sorted(HOOK_POINTS))}"
            )
        if not asyncio.iscoroutinefunction(callback):
            raise TypeError(f"Hook callback must be an async function, got {type(callback)}")
        self._hooks[hook_point].append(callback)

    def unregister(self, hook_point: str, callback: Callable | None = None) -> None:
        """Remove a hook callback (or all callbacks for a point)."""
        if hook_point not in HOOK_POINTS:
            return
        if callback is None:
            self._hooks[hook_point] = []
        else:
            self._hooks[hook_point] = [
                h for h in self._hooks[hook_point] if h is not callback
            ]

    async def execute(self, hook_point: str, *args: Any, **kwargs: Any) -> Any:
        """Execute all hooks registered for a point.

        Returns the last non-None return value from hooks, or None.
        Hooks are executed in registration order.
        Errors in hooks are caught and logged, not propagated.
        """
        if hook_point not in HOOK_POINTS:
            return None

        result = None
        for callback in self._hooks[hook_point]:
            try:
                ret = await asyncio.wait_for(
                    callback(*args, **kwargs),
                    timeout=self._timeout,
                )
                if ret is not None:
                    result = ret
                self._execution_log.append({
                    "hook_point": hook_point,
                    "callback": callback.__name__,
                    "success": True,
                })
            except asyncio.TimeoutError:
                error_msg = f"Hook {callback.__name__} timed out after {self._timeout}s"
                logger.warning(error_msg)
                self._errors.setdefault(hook_point, []).append(error_msg)
                self._execution_log.append({
                    "hook_point": hook_point,
                    "callback": callback.__name__,
                    "success": False,
                    "error": "timeout",
                })
            except Exception as e:
                error_msg = f"Hook {callback.__name__} failed: {e}"
                logger.warning(error_msg)
                self._errors.setdefault(hook_point, []).append(error_msg)
                self._execution_log.append({
                    "hook_point": hook_point,
                    "callback": callback.__name__,
                    "success": False,
                    "error": str(e),
                })

        return result

    @property
    def execution_log(self) -> list[dict]:
        return self._execution_log

    @property
    def errors(self) -> dict[str, list[str]]:
        return self._errors

    def has_hooks(self, hook_point: str) -> bool:
        return bool(self._hooks.get(hook_point))

    def clear(self) -> None:
        """Remove all hooks and reset logs."""
        for point in HOOK_POINTS:
            self._hooks[point] = []
        self._execution_log = []
        self._errors = {}
