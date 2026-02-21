import asyncio
import base64
import logging
import random
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
# Cloudflare challenge detection & solving
# ---------------------------------------------------------------------------


async def _is_cloudflare_challenge(page) -> bool:
    """Check if the current page is a Cloudflare challenge page.

    Uses a fast title check first (from CloudflareBypassForScraping), then falls
    back to DOM element and body-text scanning for edge cases.
    """
    try:
        # Fast path: Cloudflare sets title to "Just a moment..." during challenges
        title = (await page.title()).lower()
        if "just a moment" in title:
            return True

        # Quick pre-filter: if "cloudflare" isn't anywhere in the HTML, skip
        # the expensive element checks
        has_cf = await page.evaluate(
            "() => document.documentElement.innerHTML.substring(0, 10000).toLowerCase().includes('cloudflare')"
        )
        if not has_cf:
            return False

        # Check for Turnstile iframe or challenge-specific elements
        cf_selectors = [
            'iframe[src*="challenges.cloudflare.com"]',
            "#challenge-running",
            "#challenge-stage",
            ".cf-turnstile",
            "#turnstile-wrapper",
        ]
        for sel in cf_selectors:
            el = await page.query_selector(sel)
            if el:
                return True

        # Check visible body text for challenge phrases
        body_text = await page.evaluate(
            "() => (document.body && document.body.innerText || '').substring(0, 2000).toLowerCase()"
        )
        cf_phrases = [
            "verify you are human",
            "press & hold",
            "press and hold",
            "checking your browser",
            "checking if the site connection is secure",
            "please complete the captcha",
            "enable javascript and cookies to continue",
        ]
        for phrase in cf_phrases:
            if phrase in body_text:
                return True
    except Exception:
        pass
    return False


async def _detect_challenge_type(page) -> str | None:
    """Distinguish between Cloudflare challenge types.

    Returns:
        "interstitial" — passive "just a moment" page that may auto-resolve
        "turnstile"    — interactive CAPTCHA widget that needs a click
        None           — not a Cloudflare challenge
    """
    try:
        html_lower = await page.evaluate(
            "() => document.documentElement.innerHTML.substring(0, 10000).toLowerCase()"
        )
        title_lower = (await page.title()).lower()

        if "please complete the captcha" in html_lower:
            return "turnstile"

        # Check for Turnstile iframe explicitly
        iframe = await page.query_selector('iframe[src*="challenges.cloudflare.com"]')
        if iframe:
            return "turnstile"

        if "just a moment" in title_lower:
            return "interstitial"
    except Exception:
        pass
    return None


async def _solve_cloudflare_challenge(page, timeout_ms: int = 20000) -> bool:
    """Attempt to solve a Cloudflare challenge.

    Handles both interstitial (auto-resolving) and Turnstile (click) challenges.
    Returns True if the challenge was resolved (page navigated to real content).
    """
    import time

    deadline = time.monotonic() + timeout_ms / 1000
    attempt = 0

    # Step 1: Initial wait — Patchright/Camoufox often auto-pass managed
    # challenges and interstitials. The reference CloudflareBypassForScraping
    # repo uses a 5s wait here.
    initial_wait = min(5.0, (deadline - time.monotonic()) * 0.6)
    if initial_wait > 0:
        logger.info("Waiting %.1fs for potential auto-resolve...", initial_wait)
        await page.wait_for_timeout(int(initial_wait * 1000))

    # Check if already resolved after initial wait
    if not await _is_cloudflare_challenge(page):
        logger.info("Cloudflare challenge auto-resolved during initial wait")
        return True

    while time.monotonic() < deadline:
        attempt += 1
        logger.info("Cloudflare challenge solve attempt %d", attempt)

        # Determine challenge type on each attempt
        challenge_type = await _detect_challenge_type(page)
        if challenge_type is None:
            logger.info("Challenge no longer detected, resolved")
            return True

        if challenge_type == "interstitial":
            # Passive challenge — just wait for it to auto-resolve
            wait_s = min(3.0, deadline - time.monotonic())
            if wait_s > 0:
                logger.info("Interstitial challenge, waiting %.1fs for auto-resolve...", wait_s)
                await page.wait_for_timeout(int(wait_s * 1000))
            if not await _is_cloudflare_challenge(page):
                logger.info("Interstitial challenge auto-resolved on attempt %d", attempt)
                return True
            continue

        # --- Turnstile challenge: need to find and click the widget ---

        if time.monotonic() >= deadline:
            break

        # Step 2: Find the Turnstile iframe
        iframe_el = None
        for sel in [
            'iframe[src*="challenges.cloudflare.com"]',
            ".cf-turnstile iframe",
            "#turnstile-wrapper iframe",
            "#challenge-stage iframe",
        ]:
            iframe_el = await page.query_selector(sel)
            if iframe_el:
                break

        if not iframe_el:
            logger.info("No Turnstile iframe found, waiting for it to appear...")
            try:
                iframe_el = await page.wait_for_selector(
                    'iframe[src*="challenges.cloudflare.com"]',
                    timeout=min(3000, max(500, int((deadline - time.monotonic()) * 1000))),
                )
            except Exception:
                pass

        if not iframe_el:
            # No iframe — challenge may be transitioning, loop back
            await page.wait_for_timeout(500)
            continue

        # Step 3: Get iframe bounding box and click at its center
        box = await iframe_el.bounding_box()
        if not box:
            logger.info("Iframe has no bounding box, retrying...")
            await page.wait_for_timeout(500)
            continue

        # Target: center of the checkbox area (typically left side of iframe)
        target_x = box["x"] + min(box["width"] * 0.3, 30)
        target_y = box["y"] + box["height"] / 2

        # Step 4: Human-like mouse movement to target
        # Start from a random nearby position
        start_x = target_x + random.uniform(50, 120) * random.choice([-1, 1])
        start_y = target_y + random.uniform(30, 80) * random.choice([-1, 1])
        await page.mouse.move(start_x, start_y)
        await page.wait_for_timeout(random.randint(100, 250))

        # Move to target in steps (natural arc with smoothstep easing)
        steps = random.randint(12, 20)
        for i in range(1, steps + 1):
            t = i / steps
            ease_t = t * t * (3 - 2 * t)  # smoothstep
            mx = start_x + (target_x - start_x) * ease_t + random.uniform(-2, 2)
            my = start_y + (target_y - start_y) * ease_t + random.uniform(-2, 2)
            await page.mouse.move(mx, my)
            await page.wait_for_timeout(random.randint(8, 25))

        # Final move to exact target
        await page.mouse.move(target_x, target_y)
        await page.wait_for_timeout(random.randint(80, 250))

        # Step 5: Press & Hold
        logger.info("Clicking and holding Turnstile checkbox at (%.0f, %.0f)", target_x, target_y)
        await page.mouse.down()

        # Hold for 2.5-4s with micro-jitter every ~400ms
        hold_ms = random.randint(2500, 4000)
        elapsed = 0
        jitter_interval = 400
        while elapsed < hold_ms:
            wait_chunk = min(jitter_interval, hold_ms - elapsed)
            await page.wait_for_timeout(wait_chunk)
            elapsed += wait_chunk
            # Micro-jitter: small random movement while holding
            jx = target_x + random.uniform(-2, 2)
            jy = target_y + random.uniform(-2, 2)
            await page.mouse.move(jx, jy)

        await page.mouse.up()
        logger.info("Released mouse button after %dms hold", hold_ms)

        # Step 6: Wait for navigation / redirect after solving
        try:
            await page.wait_for_load_state(
                "networkidle",
                timeout=min(8000, max(1000, int((deadline - time.monotonic()) * 1000))),
            )
        except Exception:
            pass

        # Give the page a moment to settle after redirect
        await page.wait_for_timeout(1500)

        # Step 7: Check if challenge is resolved
        if not await _is_cloudflare_challenge(page):
            logger.info("Cloudflare challenge solved on attempt %d", attempt)
            return True

        logger.info("Challenge still present after attempt %d, retrying...", attempt)

    logger.warning("Cloudflare challenge not solved within timeout (%dms)", timeout_ms)
    return False


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
        logger.info("Chromium navigating to %s (timeout=%dms)", req.url, req.timeout)
        response = await page.goto(
            req.url, wait_until="domcontentloaded", timeout=req.timeout,
        )
        status_code = response.status if response else 0
        resp_headers = dict(response.headers) if response else {}
        logger.info("Chromium got status %d for %s", status_code, req.url)

        # Best-effort networkidle — let JS frameworks finish rendering
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Default JS render wait — SPAs need time to hydrate even after networkidle.
        # Use explicit wait_after_load if provided, otherwise apply a 2s default.
        wait_ms = req.wait_after_load if req.wait_after_load > 0 else 2000
        await page.wait_for_timeout(min(wait_ms, 30000))

        # Detect and solve Cloudflare challenge
        if status_code in (403, 503) or await _is_cloudflare_challenge(page):
            logger.info("Cloudflare challenge detected for %s (status=%d)", req.url, status_code)
            solved = await _solve_cloudflare_challenge(page, timeout_ms=20000)
            if solved:
                status_code = 200
                resp_headers = {}  # Original headers are stale after redirect

        # Scroll to bottom to trigger lazy-loaded content
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
        except Exception:
            pass

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
        logger.info("Chromium got %d chars HTML for %s (status=%d)", len(html), req.url, status_code)

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
        logger.info("Firefox navigating to %s (timeout=%dms)", req.url, req.timeout)
        response = await page.goto(
            req.url, wait_until="domcontentloaded", timeout=req.timeout,
        )
        status_code = response.status if response else 0
        resp_headers = dict(response.headers) if response else {}
        logger.info("Firefox got status %d for %s", status_code, req.url)

        # Best-effort networkidle — let JS frameworks finish rendering
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Default JS render wait — SPAs need time to hydrate even after networkidle.
        wait_ms = req.wait_after_load if req.wait_after_load > 0 else 2000
        await page.wait_for_timeout(min(wait_ms, 30000))

        # Detect and solve Cloudflare challenge
        if status_code in (403, 503) or await _is_cloudflare_challenge(page):
            logger.info("Cloudflare challenge detected for %s (status=%d)", req.url, status_code)
            solved = await _solve_cloudflare_challenge(page, timeout_ms=20000)
            if solved:
                status_code = 200
                resp_headers = {}  # Original headers are stale after redirect

        # Scroll to bottom to trigger lazy-loaded content
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
        except Exception:
            pass

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
        logger.info("Firefox got %d chars HTML for %s (status=%d)", len(html), req.url, status_code)

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
    # Ensure URL has a scheme (browsers require it)
    if not req.url.startswith(("http://", "https://")):
        req.url = f"https://{req.url}"

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
