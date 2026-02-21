import asyncio
import logging

from browserforge.headers import HeaderGenerator
from patchright.async_api import async_playwright, Browser, BrowserContext, Page

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ad-blocking domain list (mirrors backend/app/services/browser.py)
# ---------------------------------------------------------------------------

AD_SERVING_DOMAINS = frozenset(
    {
        "doubleclick.net",
        "adservice.google.com",
        "googlesyndication.com",
        "googletagservices.com",
        "googletagmanager.com",
        "google-analytics.com",
        "amazon-adsystem.com",
        "adnxs.com",
        "ads-twitter.com",
        "facebook.net",
        "fbcdn.net",
        "criteo.com",
        "criteo.net",
        "outbrain.com",
        "taboola.com",
        "moatads.com",
        "pubmatic.com",
        "rubiconproject.com",
        "openx.net",
        "casalemedia.com",
        "demdex.net",
        "scorecardresearch.com",
        "quantserve.com",
        "hotjar.com",
        "fullstory.com",
        "mouseflow.com",
        "newrelic.com",
        "nr-data.net",
        "adsystem.com",
        "bidswitch.net",
        "bluekai.com",
        "krxd.net",
        "advertising.com",
        "rlcdn.com",
        "smartadserver.com",
    }
)


async def _ad_block_route(route, request):
    """Abort requests to known ad/tracking domains."""
    url = request.url
    try:
        after_scheme = url.split("//", 1)[1]
        hostname = after_scheme.split("/", 1)[0].split(":")[0].lower()
    except (IndexError, ValueError):
        await route.continue_()
        return

    for domain in AD_SERVING_DOMAINS:
        if domain in hostname:
            await route.abort()
            return

    await route.continue_()


# ---------------------------------------------------------------------------
# Fingerprint generator (Bayesian — statistically accurate, not random)
# ---------------------------------------------------------------------------

_header_gen = HeaderGenerator()


# ---------------------------------------------------------------------------
# Chromium launch args — minimal set, no detection-triggering flags
# ---------------------------------------------------------------------------

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]


class StealthBrowserPool:
    """Manages Patchright Chromium + Camoufox Firefox browser pools."""

    def __init__(self):
        self._chromium: Browser | None = None
        self._playwright = None
        self._chromium_sem = asyncio.Semaphore(settings.CHROMIUM_POOL_SIZE)
        self._firefox_sem = asyncio.Semaphore(settings.FIREFOX_POOL_SIZE)
        self._init_lock = asyncio.Lock()

    async def initialize(self):
        """Launch persistent Chromium browser via Patchright."""
        async with self._init_lock:
            if self._chromium and self._chromium.is_connected():
                return
            self._playwright = await async_playwright().start()
            self._chromium = await self._playwright.chromium.launch(
                headless=settings.HEADLESS,
                args=CHROMIUM_ARGS,
            )
            logger.info(
                "Patchright Chromium launched (pool_size=%d)", settings.CHROMIUM_POOL_SIZE
            )

    async def shutdown(self):
        """Close Chromium browser and Playwright."""
        if self._chromium:
            try:
                await self._chromium.close()
            except Exception:
                pass
            self._chromium = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    # ------------------------------------------------------------------
    # Chromium (Patchright) — per-request context, persistent browser
    # ------------------------------------------------------------------

    async def acquire_chromium_page(
        self,
        proxy: dict | None = None,
        mobile: bool = False,
    ) -> tuple[BrowserContext, Page]:
        """Create a fresh BrowserContext + Page on the persistent Chromium instance.

        Caller is responsible for closing context after use.
        """
        await self.initialize()

        if not self._chromium or not self._chromium.is_connected():
            await self.initialize()

        # Generate realistic headers via BrowserForge
        headers = _header_gen.generate(browser="chrome")
        ua = headers.get("user-agent", "")

        ctx_opts: dict = {
            "user_agent": ua,
            "viewport": {"width": 375, "height": 812} if mobile else {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "light",
        }
        if proxy:
            ctx_opts["proxy"] = proxy

        context = await self._chromium.new_context(**ctx_opts)

        if settings.BLOCK_ADS:
            await context.route("**/*", _ad_block_route)

        page = await context.new_page()
        return context, page

    # ------------------------------------------------------------------
    # Firefox (Camoufox) — per-request instance via AsyncCamoufox
    # ------------------------------------------------------------------

    async def acquire_firefox_page(
        self,
        proxy: dict | None = None,
        mobile: bool = False,
    ) -> tuple:
        """Create a Camoufox Firefox browser + page.

        Returns (browser, context, page) — caller must close browser after use.
        Camoufox handles fingerprinting at C++ level automatically.
        """
        from camoufox.async_api import AsyncCamoufox

        cfox_opts: dict = {
            "headless": settings.HEADLESS,
            "geoip": True,
            "block_images": False,
        }
        if proxy:
            cfox_opts["proxy"] = proxy

        # Camoufox context manager returns a browser with built-in fingerprint
        browser = await AsyncCamoufox(**cfox_opts).__aenter__()

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        if settings.BLOCK_ADS:
            await context.route("**/*", _ad_block_route)

        page = await context.new_page()
        return browser, context, page

    # ------------------------------------------------------------------
    # Semaphore accessors
    # ------------------------------------------------------------------

    @property
    def chromium_available(self) -> int:
        """Number of available Chromium slots."""
        return self._chromium_sem._value

    @property
    def firefox_available(self) -> int:
        """Number of available Firefox slots."""
        return self._firefox_sem._value


# Module-level singleton
stealth_pool = StealthBrowserPool()
