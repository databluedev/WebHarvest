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
    """Persistent nodriver browser pool.

    Keeps a single browser + Xvfb display alive across requests.
    Each request gets its own tab — browser handles concurrent tabs.
    Browser restarts automatically after max_requests or on crash.
    Shuts down after idle_timeout seconds of inactivity.
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
            logger.info("NoDriverPool: browser started")
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
        """Open a new tab with the given URL. Returns the tab object.

        The caller MUST call release_tab() when done.
        """
        async with self._lock:
            if not await self._ensure_browser():
                return None
            self._request_count += 1
            self._last_used = time.time()

        # Navigate outside the lock so other requests can proceed
        try:
            tab = await self._browser.get(url)
            return tab
        except Exception as e:
            logger.warning("NoDriverPool: navigation failed: %s", e)
            # Browser might be dead — mark for restart
            async with self._lock:
                await self._cleanup()
            return None

    async def release_tab(self, tab):
        """Release a tab when done.

        Navigates to about:blank to free page resources instead of
        closing the tab — closing the last tab kills the browser.
        """
        if tab is None:
            return
        try:
            await tab.evaluate("window.stop(); window.location='about:blank'")
        except Exception:
            pass

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
