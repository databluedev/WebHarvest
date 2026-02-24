"""Shared nodriver (undetected Chrome + Xvfb) helper.

Provides a reusable fetch function for any service that needs to render
a page with a real headed browser that bypasses bot detection.

nodriver connects to Chrome via CDP directly (no WebDriver protocol,
no chromedriver binary). Combined with Xvfb (virtual framebuffer),
it runs a real headed browser that passes headless detection.
"""

import logging
import shutil

logger = logging.getLogger(__name__)


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
