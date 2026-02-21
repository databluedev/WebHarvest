import asyncio
import logging
import random

from browserforge.headers import HeaderGenerator
from patchright.async_api import async_playwright, Browser, BrowserContext, Page

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ad-blocking domain list
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
# Fingerprint rotation data — randomized per session for diversity
# ---------------------------------------------------------------------------

_header_gen = HeaderGenerator()

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1680, "height": 1050},
    {"width": 1280, "height": 720},
    {"width": 2560, "height": 1440},
]

MOBILE_VIEWPORTS = [
    {"width": 375, "height": 812},
    {"width": 390, "height": 844},
    {"width": 414, "height": 896},
    {"width": 360, "height": 780},
]

TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "America/Denver",
    "America/Phoenix",
    "Europe/London",
    "Europe/Paris",
]

WEBGL_RENDERERS = [
    (
        "Google Inc. (NVIDIA)",
        "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (NVIDIA)",
        "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (NVIDIA)",
        "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (Intel)",
        "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (Intel)",
        "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (AMD)",
        "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    (
        "Google Inc. (AMD)",
        "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ),
    ("Google Inc. (Apple)", "ANGLE (Apple, Apple M1, OpenGL 4.1)"),
    ("Google Inc. (Apple)", "ANGLE (Apple, Apple M2, OpenGL 4.1)"),
]

COLOR_DEPTHS = [24, 24, 24, 30, 32]


# ---------------------------------------------------------------------------
# Chromium ULTRA-STEALTH init script (20 levels)
# Patches: navigator, chrome runtime, plugins, WebGL, canvas noise,
# AudioContext, WebRTC, fonts, CDP detection, battery, sensors, etc.
# ---------------------------------------------------------------------------


def _build_chromium_stealth(
    webgl_vendor: str,
    webgl_renderer: str,
    color_depth: int,
    hw_concurrency: int,
    device_mem: int,
) -> str:
    """Build a parameterized stealth script with unique fingerprint per session."""
    return f"""
// ============================================================
// LEVEL 1: Core navigator patches
// ============================================================

// navigator.webdriver — the #1 detection vector
Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
try {{ delete navigator.__proto__.webdriver; }} catch(e) {{}}

// navigator.languages
Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});

// navigator.platform consistency with UA
const ua = navigator.userAgent;
if (ua.includes('Win')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'Win32' }});
}} else if (ua.includes('Mac')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'MacIntel' }});
}} else if (ua.includes('Linux')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'Linux x86_64' }});
}}

// Hardware fingerprint — consistent per session
Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw_concurrency} }});
Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {device_mem} }});
Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => 0 }});

// ============================================================
// LEVEL 2: Chrome runtime (missing in headless = instant detection)
// ============================================================

window.chrome = {{
    runtime: {{
        PlatformOs: {{ MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' }},
        PlatformArch: {{ ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' }},
        PlatformNaclArch: {{ ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' }},
        RequestUpdateCheckStatus: {{ THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' }},
        OnInstalledReason: {{ INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' }},
        OnRestartRequiredReason: {{ APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }},
        connect: function() {{}},
        sendMessage: function() {{}},
        id: undefined,
    }},
    loadTimes: function() {{
        return {{
            requestTime: Date.now() / 1000 - Math.random() * 3,
            startLoadTime: Date.now() / 1000 - Math.random() * 2,
            commitLoadTime: Date.now() / 1000 - Math.random(),
            finishDocumentLoadTime: Date.now() / 1000,
            finishLoadTime: Date.now() / 1000,
            firstPaintTime: Date.now() / 1000,
            firstPaintAfterLoadTime: 0,
            navigationType: 'Other',
            wasFetchedViaSpdy: false,
            wasNpnNegotiated: true,
            npnNegotiatedProtocol: 'h2',
            wasAlternateProtocolAvailable: false,
            connectionInfo: 'h2',
        }};
    }},
    csi: function() {{
        return {{
            onloadT: Date.now(),
            pageT: Math.random() * 3000 + 1000,
            startE: Date.now() - Math.random() * 5000,
            tran: 15,
        }};
    }},
}};

// ============================================================
// LEVEL 3: Plugins (headless has 0 plugins = detection)
// ============================================================

const makePlugin = (name, desc, filename) => {{
    const plugin = Object.create(Plugin.prototype);
    Object.defineProperties(plugin, {{
        name: {{ value: name, enumerable: true }},
        description: {{ value: desc, enumerable: true }},
        filename: {{ value: filename, enumerable: true }},
        length: {{ value: 1, enumerable: true }},
    }});
    return plugin;
}};

const plugins = [
    makePlugin('Chrome PDF Plugin', 'Portable Document Format', 'internal-pdf-viewer'),
    makePlugin('Chrome PDF Viewer', '', 'mhjfbmdgcfjbbpaeojofohoefgiehjai'),
    makePlugin('Native Client', '', 'internal-nacl-plugin'),
];

Object.defineProperty(navigator, 'plugins', {{
    get: () => {{
        const arr = Object.create(PluginArray.prototype);
        plugins.forEach((p, i) => {{ arr[i] = p; }});
        Object.defineProperty(arr, 'length', {{ value: plugins.length }});
        arr.item = (i) => plugins[i];
        arr.namedItem = (name) => plugins.find(p => p.name === name);
        arr.refresh = () => {{}};
        return arr;
    }},
}});

// ============================================================
// LEVEL 4: WebGL fingerprint (unique per session)
// ============================================================

const glVendor = '{webgl_vendor}';
const glRenderer = '{webgl_renderer}';

const patchWebGL = (proto) => {{
    if (!proto) return;
    const orig = proto.getParameter;
    proto.getParameter = function(param) {{
        if (param === 37445) return glVendor;
        if (param === 37446) return glRenderer;
        return orig.call(this, param);
    }};
    const origExt = proto.getExtension;
    proto.getExtension = function(name) {{
        if (name === 'WEBGL_debug_renderer_info') {{
            return {{ UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 }};
        }}
        return origExt.call(this, name);
    }};
}};
patchWebGL(WebGLRenderingContext.prototype);
if (window.WebGL2RenderingContext) patchWebGL(WebGL2RenderingContext.prototype);

// ============================================================
// LEVEL 5: Canvas fingerprint noise injection
// ============================================================

(function() {{
    const seed = {random.randint(1, 2**31)};
    let s = seed;
    function nextRand() {{
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF;
        return (s >>> 0) / 0xFFFFFFFF;
    }}

    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            try {{
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                const pixels = imageData.data;
                for (let i = 0; i < Math.min(pixels.length, 100); i += 4) {{
                    if (nextRand() < 0.1) {{
                        pixels[i] = Math.max(0, Math.min(255, pixels[i] + (nextRand() < 0.5 ? 1 : -1)));
                    }}
                }}
                ctx.putImageData(imageData, 0, 0);
            }} catch(e) {{}}
        }}
        return origToDataURL.apply(this, arguments);
    }};

    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            try {{
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                const pixels = imageData.data;
                for (let i = 0; i < Math.min(pixels.length, 100); i += 4) {{
                    if (nextRand() < 0.1) {{
                        pixels[i] = Math.max(0, Math.min(255, pixels[i] + (nextRand() < 0.5 ? 1 : -1)));
                    }}
                }}
                ctx.putImageData(imageData, 0, 0);
            }} catch(e) {{}}
        }}
        return origToBlob.apply(this, arguments);
    }};
}})();

// ============================================================
// LEVEL 6: AudioContext fingerprint spoofing
// ============================================================

(function() {{
    const audioSeed = {random.randint(1, 2**31)};
    if (window.OfflineAudioContext || window.webkitOfflineAudioContext) {{
        const AudioCtx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
        const origCreateOscillator = AudioCtx.prototype.createOscillator;
        AudioCtx.prototype.createOscillator = function() {{
            const osc = origCreateOscillator.call(this);
            const origConnect = osc.connect.bind(osc);
            osc.connect = function(dest) {{
                const result = origConnect(dest);
                try {{
                    const gain = osc.context.createGain();
                    gain.gain.value = 0.99 + (audioSeed % 100) / 10000;
                    origConnect(gain);
                    gain.connect(dest);
                }} catch(e) {{}}
                return result;
            }};
            return osc;
        }};
    }}
}})();

// ============================================================
// LEVEL 7: WebRTC IP leak prevention
// ============================================================

(function() {{
    const origRTC = window.RTCPeerConnection || window.webkitRTCPeerConnection || window.mozRTCPeerConnection;
    if (origRTC) {{
        const newRTC = function(config) {{
            if (config && config.iceServers) {{
                config.iceTransportPolicy = 'relay';
            }}
            return new origRTC(config);
        }};
        newRTC.prototype = origRTC.prototype;
        window.RTCPeerConnection = newRTC;
        if (window.webkitRTCPeerConnection) window.webkitRTCPeerConnection = newRTC;
    }}
}})();

// ============================================================
// LEVEL 8: Permissions API
// ============================================================

(function() {{
    const origQuery = window.Permissions?.prototype?.query;
    if (origQuery) {{
        window.Permissions.prototype.query = function(params) {{
            if (params?.name === 'notifications') {{
                return Promise.resolve({{ state: 'default' }});
            }}
            return origQuery.call(this, params);
        }};
    }}
}})();

// ============================================================
// LEVEL 9: Screen & display consistency
// ============================================================

(function() {{
    const w = window.outerWidth || screen.width || 1920;
    const h = window.outerHeight || screen.height || 1080;
    try {{
        Object.defineProperty(screen, 'availWidth', {{ get: () => w }});
        Object.defineProperty(screen, 'availHeight', {{ get: () => h - 40 }});
        Object.defineProperty(screen, 'width', {{ get: () => w }});
        Object.defineProperty(screen, 'height', {{ get: () => h }});
        Object.defineProperty(screen, 'colorDepth', {{ get: () => {color_depth} }});
        Object.defineProperty(screen, 'pixelDepth', {{ get: () => {color_depth} }});
        Object.defineProperty(screen, 'availLeft', {{ get: () => 0 }});
        Object.defineProperty(screen, 'availTop', {{ get: () => 0 }});
    }} catch(e) {{}}
    Object.defineProperty(window, 'devicePixelRatio', {{ get: () => 1 }});
}})();

// ============================================================
// LEVEL 10: Connection type spoofing
// ============================================================

if (navigator.connection) {{
    try {{
        Object.defineProperty(navigator.connection, 'rtt', {{ get: () => {random.choice([50, 75, 100, 150])} }});
        Object.defineProperty(navigator.connection, 'downlink', {{ get: () => {random.choice([10, 15, 20, 50])} }});
        Object.defineProperty(navigator.connection, 'effectiveType', {{ get: () => '4g' }});
        Object.defineProperty(navigator.connection, 'saveData', {{ get: () => false }});
    }} catch(e) {{}}
}}

// ============================================================
// LEVEL 11: Notification.permission
// ============================================================

try {{
    Object.defineProperty(Notification, 'permission', {{ get: () => 'default' }});
}} catch(e) {{}}

// ============================================================
// LEVEL 12: Hide ALL automation properties
// ============================================================

(function() {{
    const props = [
        'domAutomation', 'domAutomationController',
        '_selenium', '_Selenium_IDE_Recorder',
        '__webdriver_script_fn', '__driver_evaluate',
        '__webdriver_evaluate', '__fxdriver_evaluate',
        '__driver_unwrapped', '__webdriver_unwrapped',
        '__fxdriver_unwrapped', '__selenium_unwrapped',
        '_WEBDRIVER_ELEM_CACHE', 'callSelenium',
        'calledSelenium', '_phantom', '__nightmare',
        'cdc_adoQpoasnfa76pfcZLmcfl_Array',
        'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
        'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
        'cdc_adoQpoasnfa76pfcZLmcfl_JSON',
        'cdc_adoQpoasnfa76pfcZLmcfl_Object',
    ];
    props.forEach(p => {{
        try {{ delete window[p]; }} catch(e) {{}}
        try {{ Object.defineProperty(window, p, {{ get: () => undefined }}); }} catch(e) {{}}
    }});
    props.forEach(p => {{
        try {{ delete document[p]; }} catch(e) {{}}
    }});
}})();

// ============================================================
// LEVEL 13: CDP detection prevention
// ============================================================

(function() {{
    const origPrepare = Error.prepareStackTrace;
    if (origPrepare) {{
        Error.prepareStackTrace = function(err, stack) {{
            const filtered = stack.filter(frame => {{
                const fn = frame.getFunctionName() || '';
                const file = frame.getFileName() || '';
                return !fn.includes('Runtime') && !file.includes('pptr') && !file.includes('playwright');
            }});
            return origPrepare(err, filtered);
        }};
    }}
}})();

// ============================================================
// LEVEL 14: Media codecs (headless may differ)
// ============================================================

if (window.MediaSource) {{
    const origIsTypeSupported = MediaSource.isTypeSupported;
    MediaSource.isTypeSupported = function(type) {{
        if (type.includes('video/mp4')) return true;
        if (type.includes('video/webm')) return true;
        if (type.includes('audio/mp4')) return true;
        if (type.includes('audio/webm')) return true;
        return origIsTypeSupported.call(this, type);
    }};
}}

// ============================================================
// LEVEL 15: iframe contentWindow protection
// ============================================================

try {{
    const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
    if (elementDescriptor) {{
        Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {{
            ...elementDescriptor,
            get: function() {{
                if (this.id === 'modernizr') return 1;
                return elementDescriptor.get.call(this);
            }},
        }});
    }}
}} catch(e) {{}}

// ============================================================
// LEVEL 16: Battery API spoofing
// ============================================================

if (navigator.getBattery) {{
    navigator.getBattery = function() {{
        return Promise.resolve({{
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: {round(random.uniform(0.5, 1.0), 2)},
            addEventListener: function() {{}},
            removeEventListener: function() {{}},
        }});
    }};
}}

// ============================================================
// LEVEL 17: Speech synthesis voices
// ============================================================

if (window.speechSynthesis) {{
    const origGetVoices = speechSynthesis.getVoices;
    speechSynthesis.getVoices = function() {{
        const voices = origGetVoices.call(this);
        if (voices.length === 0) {{
            return [
                {{ default: true, lang: 'en-US', localService: true, name: 'Google US English', voiceURI: 'Google US English' }},
                {{ default: false, lang: 'en-GB', localService: true, name: 'Google UK English Female', voiceURI: 'Google UK English Female' }},
                {{ default: false, lang: 'en-US', localService: true, name: 'Google US English Male', voiceURI: 'Google US English Male' }},
            ];
        }}
        return voices;
    }};
}}

// ============================================================
// LEVEL 18: Keyboard & Input event consistency
// ============================================================

(function() {{
    const origAddEvent = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, fn, options) {{
        if (type === 'keydown' || type === 'keyup' || type === 'keypress') {{
            const wrappedFn = function(e) {{
                if (!e.isTrusted) {{
                    const fakeEvent = new KeyboardEvent(e.type, {{
                        key: e.key,
                        code: e.code,
                        keyCode: e.keyCode,
                        which: e.which,
                        bubbles: true,
                        cancelable: true,
                    }});
                    Object.defineProperty(fakeEvent, 'isTrusted', {{ get: () => true }});
                    return fn.call(this, fakeEvent);
                }}
                return fn.call(this, e);
            }};
            return origAddEvent.call(this, type, wrappedFn, options);
        }}
        return origAddEvent.call(this, type, fn, options);
    }};
}})();

// ============================================================
// LEVEL 19: Document visibility
// ============================================================

Object.defineProperty(document, 'hidden', {{ get: () => false }});
Object.defineProperty(document, 'visibilityState', {{ get: () => 'visible' }});

// ============================================================
// LEVEL 20: Performance.now() noise
// ============================================================

(function() {{
    const origNow = Performance.prototype.now;
    Performance.prototype.now = function() {{
        return origNow.call(this) + Math.random() * 0.1;
    }};
}})();
"""


# ---------------------------------------------------------------------------
# Chromium launch args
# ---------------------------------------------------------------------------

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    # Prevent sandbox issues in Docker
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]


# ---------------------------------------------------------------------------
# Stealth browser pool
# ---------------------------------------------------------------------------


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
                channel="chrome",
                args=CHROMIUM_ARGS,
            )
            logger.info(
                "Patchright Chrome launched (pool_size=%d)", settings.CHROMIUM_POOL_SIZE
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
        """Create a fresh BrowserContext + Page with full stealth on persistent Chromium.

        Each request gets:
        - Randomized viewport, timezone, locale
        - Unique fingerprint (WebGL, canvas, audio, hardware)
        - 20-level stealth init script
        - Sec-CH-UA headers matching user agent
        - Ad/tracker blocking
        """
        await self.initialize()

        if not self._chromium or not self._chromium.is_connected():
            await self.initialize()

        # Generate realistic headers via BrowserForge (Bayesian model)
        headers = _header_gen.generate(browser="chrome")
        ua = headers.get("user-agent", "")

        # Randomize fingerprint per session
        vp = random.choice(MOBILE_VIEWPORTS) if mobile else random.choice(VIEWPORTS)
        tz = random.choice(TIMEZONES)
        hw_concurrency = random.choice([4, 8, 12, 16])
        device_mem = random.choice([4, 8, 16])
        webgl_vendor, webgl_renderer = random.choice(WEBGL_RENDERERS)
        color_depth = random.choice(COLOR_DEPTHS)

        # Build Sec-CH-UA to match the UA string
        if "Win" in ua:
            ch_platform = '"Windows"'
        elif "Mac" in ua:
            ch_platform = '"macOS"'
        else:
            ch_platform = '"Linux"'

        ctx_opts: dict = {
            "user_agent": ua,
            "viewport": vp,
            "locale": "en-US",
            "timezone_id": tz,
            "color_scheme": "light",
            "ignore_https_errors": True,
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": ch_platform,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        }
        if proxy:
            ctx_opts["proxy"] = proxy

        context = await self._chromium.new_context(**ctx_opts)

        # Inject 20-level stealth script BEFORE any page loads
        stealth_script = _build_chromium_stealth(
            webgl_vendor, webgl_renderer, color_depth, hw_concurrency, device_mem,
        )
        await context.add_init_script(stealth_script)

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
            "headless": "virtual" if settings.HEADLESS else False,
            "geoip": True,
            "humanize": True,
            "block_images": False,
            "block_webrtc": True,
            "os": random.choice(["windows", "linux"]),
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
