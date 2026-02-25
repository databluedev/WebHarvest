"""Shared nodriver (undetected Chrome + Xvfb) helper.

Provides a reusable fetch function for any service that needs to render
a page with a real headed browser that bypasses bot detection.

nodriver connects to Chrome via CDP directly (no WebDriver protocol,
no chromedriver binary). Combined with Xvfb (virtual framebuffer),
it runs a real headed browser that passes headless detection.

Includes a persistent browser pool (NoDriverPool) that keeps a browser
alive across requests to eliminate the 5-10s startup cost. Subsequent
requests complete in ~3-5s instead of 10-15s.
"""

import asyncio
import logging
import shutil
import time

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Persistent browser pool
# ═══════════════════════════════════════════════════════════════════


class NoDriverPool:
    """Persistent nodriver browser pool with tab recycling.

    Keeps a single browser + Xvfb display alive across requests.
    Released tabs are recycled (navigated to about:blank, handlers
    cleared) and reused by subsequent requests — this avoids both
    the zombie-tab memory leak *and* nodriver's tab.close() bugs.

    Concurrency safety:
    - ``_tab_semaphore`` limits simultaneous open tabs (prevents
      Chrome OOM when many users hit the API at once).
    - ``_generation`` counter prevents a stale error handler from
      killing a *new* browser that replaced the one it was using.
    """

    _instance: "NoDriverPool | None" = None

    def __init__(self):
        self._browser = None
        self._display = None
        self._lock = asyncio.Lock()
        self._request_count = 0
        self._max_requests = 200  # restart browser after this many
        self._last_used = 0.0
        self._idle_timeout = 300  # 5 minutes
        self._starting = False
        self._generation = 0  # incremented on every browser start
        self._tab_semaphore = asyncio.Semaphore(6)  # max concurrent tabs
        self._idle_tabs: list = []  # recycled tabs at about:blank

    @classmethod
    def get(cls) -> "NoDriverPool":
        """Get the singleton pool instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _start_browser(self) -> bool:
        """Start the browser + display. Must hold _lock."""
        try:
            import nodriver as uc
            from pyvirtualdisplay import Display

            chrome_path = find_chrome_binary()
            if not chrome_path:
                logger.warning("NoDriverPool: no Chrome binary found")
                return False

            # Start virtual display
            self._display = Display(visible=False, size=(1920, 1080))
            self._display.start()
            logger.info(
                "NoDriverPool: Xvfb started on display :%s",
                self._display.display,
            )

            # Start browser
            self._browser = await uc.start(
                headless=False,
                browser_executable_path=chrome_path,
                sandbox=False,
                lang="en-US",
                browser_args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--window-size=1920,1080",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
            )
            self._request_count = 0
            self._last_used = time.time()
            self._generation += 1
            logger.info("NoDriverPool: browser started (gen=%d)", self._generation)
            return True

        except Exception as e:
            logger.warning("NoDriverPool: failed to start browser: %s", e)
            await self._cleanup()
            return False

    async def _cleanup(self):
        """Stop browser and display. Must hold _lock."""
        if self._browser:
            try:
                self._browser.stop()
            except Exception:
                pass
            self._browser = None

        if self._display:
            try:
                self._display.stop()
            except Exception:
                pass
            self._display = None

        self._request_count = 0
        self._idle_tabs.clear()  # all tabs are dead after browser stop
        logger.info("NoDriverPool: cleaned up")

    async def _ensure_browser(self) -> bool:
        """Ensure browser is running. Must hold _lock."""
        # Check if browser needs restart
        if self._browser and self._request_count >= self._max_requests:
            logger.info("NoDriverPool: restarting after %d requests", self._request_count)
            await self._cleanup()

        if self._browser is None:
            return await self._start_browser()

        # Quick health check — ping the browser connection
        try:
            from nodriver import cdp

            await self._browser.connection.send(
                cdp.target.get_targets(), _is_update=True
            )
        except Exception:
            logger.warning("NoDriverPool: browser unhealthy, restarting")
            await self._cleanup()
            return await self._start_browser()

        return True

    async def acquire_tab(self, url: str):
        """Get a tab navigated to *url*. Returns the tab object.

        Reuses a recycled idle tab when available (avoids creating
        new tabs and the zombie-tab leak). Falls back to opening
        a new tab via ``browser.get()``.

        The caller MUST call ``release_tab()`` when done.
        Blocks if the max-concurrent-tab limit is reached.
        """
        await self._tab_semaphore.acquire()

        async with self._lock:
            if not await self._ensure_browser():
                self._tab_semaphore.release()
                return None
            self._request_count += 1
            gen = self._generation
            self._last_used = time.time()

        # Try to reuse a recycled tab (already at about:blank).
        while self._idle_tabs:
            candidate = self._idle_tabs.pop()
            try:
                await candidate.get(url)
                return candidate
            except Exception:
                pass  # Dead tab (browser restarted, etc.) — skip it

        # No reusable tabs — create a new one
        try:
            tab = await self._browser.get(url)
            return tab
        except Exception as e:
            logger.warning("NoDriverPool: navigation failed: %s", e)
            # Only cleanup if the browser hasn't already been replaced
            # by another coroutine (generation check prevents cascade kills).
            async with self._lock:
                if self._generation == gen:
                    await self._cleanup()
            self._tab_semaphore.release()
            return None

    async def release_tab(self, tab):
        """Release a tab for recycling.

        Navigates to about:blank (frees page resources), clears CDP
        event handlers, and adds the tab to the idle pool for reuse.
        Does NOT call ``tab.close()`` — nodriver corrupts its internal
        target list when tabs are closed, causing StopIteration errors.
        """
        if tab is None:
            return
        try:
            # Disable CDP network monitoring (stop capturing events)
            try:
                from nodriver import cdp
                await asyncio.wait_for(
                    tab.send(cdp.network.disable()), timeout=2,
                )
            except Exception:
                pass
            # Navigate to blank to free page resources
            await asyncio.wait_for(
                tab.evaluate("window.stop(); window.location='about:blank'"),
                timeout=2,
            )
            # Clear event handlers so stale closures don't accumulate
            if hasattr(tab, 'handlers'):
                tab.handlers.clear()
            self._idle_tabs.append(tab)
        except Exception:
            pass  # Tab is dead — don't recycle, just drop it
        finally:
            self._tab_semaphore.release()

    async def shutdown(self):
        """Shutdown the pool completely."""
        async with self._lock:
            await self._cleanup()

    @property
    def is_warm(self) -> bool:
        """True if the browser is already running."""
        return self._browser is not None


def find_chrome_binary() -> str | None:
    """Find a usable Chrome/Chromium binary on the system."""
    candidates = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
    ]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


async def fetch_page_nodriver(
    url: str,
    *,
    wait_selector: str | None = None,
    wait_selector_fallback: str | None = None,
    wait_time: float = 3,
    screenshot: bool = False,
    try_cf_bypass: bool = False,
) -> tuple[str | None, str | None]:
    """Fetch a page using nodriver with Xvfb virtual display.

    Args:
        url: URL to fetch.
        wait_selector: CSS selector to wait for before grabbing HTML.
        wait_selector_fallback: Fallback selector if primary doesn't appear.
        wait_time: Seconds to sleep after load (lets JS settle).
        screenshot: If True, capture a PNG screenshot (base64).
        try_cf_bypass: If True, attempt Cloudflare challenge bypass.

    Returns:
        (html, screenshot_b64) — either may be None on failure.
    """
    display = None
    try:
        import nodriver as uc
        from nodriver import cdp
        from pyvirtualdisplay import Display

        chrome_path = find_chrome_binary()
        if not chrome_path:
            logger.warning("No Chrome/Chromium binary found for nodriver")
            return None, None

        # Start virtual display (Xvfb) for headed mode
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        logger.debug("Xvfb started on display :%s", display.display)

        browser = await uc.start(
            headless=False,
            browser_executable_path=chrome_path,
            sandbox=False,
            lang="en-US",
            browser_args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,1080",
                "--disable-gpu",
            ],
        )

        try:
            tab = await browser.get(url)

            # Wait for specific content selector
            if wait_selector:
                try:
                    await tab.select(wait_selector, timeout=10)
                except Exception:
                    if wait_selector_fallback:
                        try:
                            await tab.select(wait_selector_fallback, timeout=8)
                        except Exception:
                            pass

            # Let remaining JS settle
            await tab.sleep(wait_time)

            # Cloudflare challenge bypass
            if try_cf_bypass:
                page_text = ""
                try:
                    page_text = await tab.evaluate(
                        "document.body.innerText || ''"
                    )
                except Exception:
                    pass
                cf_patterns = [
                    "checking your browser",
                    "just a moment",
                    "verify you are human",
                    "attention required",
                ]
                if any(p in (page_text or "").lower() for p in cf_patterns):
                    logger.info("Cloudflare challenge detected, attempting bypass")
                    try:
                        await tab.verify_cf()
                        await tab.sleep(3)
                    except Exception as e:
                        logger.debug("CF bypass attempt: %s", e)

            # Get full page HTML
            html = await tab.get_content()
            if not html:
                html = await tab.evaluate(
                    "document.documentElement.outerHTML"
                )

            # Screenshot via CDP
            screenshot_b64 = None
            if screenshot:
                try:
                    screenshot_b64 = await tab.send(
                        cdp.page.capture_screenshot(format_="png")
                    )
                except Exception as e:
                    logger.debug("nodriver screenshot failed: %s", e)

            logger.info(
                "nodriver fetch: %d chars, %d divs",
                len(html) if html else 0,
                html.count("<div") if html else 0,
            )
            return html, screenshot_b64

        finally:
            browser.stop()

    except Exception as e:
        logger.warning("nodriver fetch failed for %s: %s", url, e)
        return None, None
    finally:
        if display:
            try:
                display.stop()
            except Exception:
                pass
