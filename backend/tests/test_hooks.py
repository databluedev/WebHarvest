"""Tests for the hook lifecycle system."""
import asyncio
import pytest
from app.services.hooks import HookManager, HOOK_POINTS


class TestHookManager:
    @pytest.mark.asyncio
    async def test_register_and_execute(self):
        hm = HookManager()
        called = False

        async def my_hook(page, url):
            nonlocal called
            called = True

        hm.register("before_goto", my_hook)
        await hm.execute("before_goto", None, "https://example.com")
        assert called

    @pytest.mark.asyncio
    async def test_hook_return_value(self):
        hm = HookManager()

        async def my_hook():
            return "modified"

        hm.register("before_return", my_hook)
        result = await hm.execute("before_return")
        assert result == "modified"

    @pytest.mark.asyncio
    async def test_hook_error_isolation(self):
        hm = HookManager()
        good_called = False

        async def bad_hook():
            raise ValueError("Hook error")

        async def good_hook():
            nonlocal good_called
            good_called = True

        hm.register("before_return", bad_hook)
        hm.register("before_return", good_hook)
        await hm.execute("before_return")
        assert good_called
        assert len(hm.errors.get("before_return", [])) == 1

    @pytest.mark.asyncio
    async def test_hook_timeout(self):
        hm = HookManager(timeout=0.1)

        async def slow_hook():
            await asyncio.sleep(5)

        hm.register("before_goto", slow_hook)
        await hm.execute("before_goto")
        assert len(hm.errors.get("before_goto", [])) == 1

    def test_invalid_hook_point(self):
        hm = HookManager()

        async def my_hook():
            pass

        with pytest.raises(ValueError):
            hm.register("invalid_point", my_hook)

    def test_sync_function_rejected(self):
        hm = HookManager()

        def sync_hook():
            pass

        with pytest.raises(TypeError):
            hm.register("before_goto", sync_hook)

    @pytest.mark.asyncio
    async def test_unregister(self):
        hm = HookManager()
        called = False

        async def my_hook():
            nonlocal called
            called = True

        hm.register("before_return", my_hook)
        hm.unregister("before_return", my_hook)
        await hm.execute("before_return")
        assert not called

    @pytest.mark.asyncio
    async def test_clear(self):
        hm = HookManager()

        async def my_hook():
            pass

        hm.register("before_goto", my_hook)
        hm.register("after_goto", my_hook)
        hm.clear()
        assert not hm.has_hooks("before_goto")
        assert not hm.has_hooks("after_goto")

    def test_has_hooks(self):
        hm = HookManager()

        async def my_hook():
            pass

        assert not hm.has_hooks("before_goto")
        hm.register("before_goto", my_hook)
        assert hm.has_hooks("before_goto")
