import asyncio
import base64
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from browser_pool import stealth_pool
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ScrapeRequest(BaseModel):
    url: str
    timeout: int = Field(default=30000, description="Navigation timeout in ms")
    wait_after_load: int = Field(default=0, description="Extra wait after load in ms")
    use_firefox: bool = False
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    actions: list[dict] | None = None
    screenshot: bool = False
    mobile: bool = False
    proxy: dict | None = None


class ScrapeResponse(BaseModel):
    html: str = ""
    status_code: int = 0
    screenshot: str | None = None
    action_screenshots: list[str] = []
    response_headers: dict[str, str] = {}
    success: bool = True
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    chromium_available: int = 0
    firefox_available: int = 0


# ---------------------------------------------------------------------------
# Action executor (direct port of BrowserPool.execute_actions)
# ---------------------------------------------------------------------------


async def execute_actions(page, actions: list[dict]) -> list[str]:
    """Execute browser actions on the page. Returns list of screenshot b64 strings."""
    screenshots = []
    for action in actions:
        action_type = action.get("type", "")
        try:
            if action_type == "click":
                selector = action.get("selector", "")
                if selector:
                    kwargs = {"timeout": 5000}
                    if action.get("button"):
                        kwargs["button"] = action["button"]
                    if action.get("click_count"):
                        kwargs["click_count"] = action["click_count"]
                    if action.get("modifiers"):
                        kwargs["modifiers"] = action["modifiers"]
                    await page.click(selector, **kwargs)

            elif action_type == "type":
                selector = action.get("selector", "")
                text = action.get("text", "")
                if selector and text:
                    await page.type(selector, text, delay=50)

            elif action_type == "fill":
                selector = action.get("selector", "")
                text = action.get("text", "")
                if selector and text:
                    await page.fill(selector, text)

            elif action_type == "wait":
                ms = action.get("milliseconds", 1000)
                await page.wait_for_timeout(min(ms, 30000))

            elif action_type == "scroll":
                direction = action.get("direction", "down")
                amount = action.get("amount", 500)
                delta = amount if direction == "down" else -amount
                await page.mouse.wheel(0, delta)
                await page.wait_for_timeout(500)

            elif action_type == "screenshot":
                ss = await page.screenshot(type="png")
                screenshots.append(base64.b64encode(ss).decode())

            elif action_type == "hover":
                selector = action.get("selector", "")
                if selector:
                    await page.hover(selector, timeout=5000)

            elif action_type == "press":
                key = action.get("key", "")
                selector = action.get("selector")
                if key:
                    if selector:
                        await page.press(selector, key, timeout=5000)
                    else:
                        await page.keyboard.press(key)

            elif action_type == "select":
                selector = action.get("selector", "")
                value = action.get("value", "")
                if selector and value:
                    await page.select_option(selector, value=value, timeout=5000)

            elif action_type == "fill_form":
                fields = action.get("fields", {})
                for field_selector, field_value in fields.items():
                    try:
                        await page.fill(field_selector, field_value, timeout=3000)
                    except Exception:
                        try:
                            await page.type(field_selector, field_value, delay=30, timeout=3000)
                        except Exception:
                            pass
                await page.wait_for_timeout(200)

            elif action_type == "evaluate":
                script = action.get("script", "")
                if script:
                    await page.evaluate(script)

            elif action_type == "go_back":
                await page.go_back(timeout=10000)

            elif action_type == "go_forward":
                await page.go_forward(timeout=10000)

            elif action_type == "wait_for_selector":
                selector = action.get("selector", "")
                ms = action.get("milliseconds", 10000)
                if selector:
                    await page.wait_for_selector(selector, timeout=ms)

            elif action_type == "wait_for_navigation":
                ms = action.get("milliseconds", 10000)
                await page.wait_for_load_state("domcontentloaded", timeout=ms)

            elif action_type == "focus":
                selector = action.get("selector", "")
                if selector:
                    await page.focus(selector, timeout=5000)

            elif action_type == "clear":
                selector = action.get("selector", "")
                if selector:
                    await page.fill(selector, "", timeout=5000)

        except Exception as e:
            logger.warning("Action '%s' failed: %s", action_type, e)

    return screenshots


# ---------------------------------------------------------------------------
# Core scrape logic
# ---------------------------------------------------------------------------


async def _scrape_chromium(req: ScrapeRequest) -> ScrapeResponse:
    """Scrape using Patchright Chromium."""
    context = None
    try:
        context, page = await stealth_pool.acquire_chromium_page(
            proxy=req.proxy, mobile=req.mobile,
        )

        # Inject cookies
        if req.cookies:
            from urllib.parse import urlparse
            domain = urlparse(req.url).netloc
            await context.add_cookies(
                [{"name": k, "value": v, "domain": domain, "path": "/"} for k, v in req.cookies.items()]
            )

        # Inject custom headers
        if req.headers:
            await page.set_extra_http_headers(req.headers)

        # Navigate
        response = await page.goto(
            req.url, wait_until="domcontentloaded", timeout=req.timeout,
        )
        status_code = response.status if response else 0
        resp_headers = dict(response.headers) if response else {}

        # Best-effort networkidle
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # Extra wait
        if req.wait_after_load > 0:
            await page.wait_for_timeout(min(req.wait_after_load, 30000))

        # Execute actions
        action_screenshots = []
        if req.actions:
            action_screenshots = await execute_actions(page, req.actions)

        # Screenshot
        screenshot_b64 = None
        if req.screenshot:
            ss = await page.screenshot(type="png", full_page=True)
            screenshot_b64 = base64.b64encode(ss).decode()

        html = await page.content()

        return ScrapeResponse(
            html=html,
            status_code=status_code,
            screenshot=screenshot_b64,
            action_screenshots=action_screenshots,
            response_headers=resp_headers,
            success=True,
        )
    except Exception as e:
        logger.error("Chromium scrape failed for %s: %s", req.url, e)
        return ScrapeResponse(success=False, error=str(e))
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass


async def _scrape_firefox(req: ScrapeRequest) -> ScrapeResponse:
    """Scrape using Camoufox Firefox."""
    browser = None
    try:
        browser, context, page = await stealth_pool.acquire_firefox_page(
            proxy=req.proxy, mobile=req.mobile,
        )

        # Inject cookies
        if req.cookies:
            from urllib.parse import urlparse
            domain = urlparse(req.url).netloc
            await context.add_cookies(
                [{"name": k, "value": v, "domain": domain, "path": "/"} for k, v in req.cookies.items()]
            )

        # Inject custom headers
        if req.headers:
            await page.set_extra_http_headers(req.headers)

        # Navigate
        response = await page.goto(
            req.url, wait_until="domcontentloaded", timeout=req.timeout,
        )
        status_code = response.status if response else 0
        resp_headers = dict(response.headers) if response else {}

        # Best-effort networkidle
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # Extra wait
        if req.wait_after_load > 0:
            await page.wait_for_timeout(min(req.wait_after_load, 30000))

        # Execute actions
        action_screenshots = []
        if req.actions:
            action_screenshots = await execute_actions(page, req.actions)

        # Screenshot
        screenshot_b64 = None
        if req.screenshot:
            ss = await page.screenshot(type="png", full_page=True)
            screenshot_b64 = base64.b64encode(ss).decode()

        html = await page.content()

        return ScrapeResponse(
            html=html,
            status_code=status_code,
            screenshot=screenshot_b64,
            action_screenshots=action_screenshots,
            response_headers=resp_headers,
            success=True,
        )
    except Exception as e:
        logger.error("Firefox scrape failed for %s: %s", req.url, e)
        return ScrapeResponse(success=False, error=str(e))
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize browser pool on startup, close on shutdown."""
    await stealth_pool.initialize()
    logger.info("Stealth engine ready on port %d", settings.PORT)
    yield
    await stealth_pool.shutdown()
    logger.info("Stealth engine shut down")


app = FastAPI(title="Stealth Engine", lifespan=lifespan)


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    """Scrape a URL using stealth Chromium or Camoufox Firefox."""
    sem = stealth_pool._firefox_sem if req.use_firefox else stealth_pool._chromium_sem
    engine = "Firefox" if req.use_firefox else "Chromium"

    try:
        await asyncio.wait_for(sem.acquire(), timeout=30.0)
    except asyncio.TimeoutError:
        return ScrapeResponse(
            success=False,
            error=f"No {engine} slots available (timeout 30s)",
        )

    try:
        if req.use_firefox:
            return await _scrape_firefox(req)
        else:
            return await _scrape_chromium(req)
    finally:
        sem.release()


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check with pool availability."""
    return HealthResponse(
        status="healthy",
        chromium_available=stealth_pool.chromium_available,
        firefox_available=stealth_pool.firefox_available,
    )
