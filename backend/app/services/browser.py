import asyncio
import base64
import logging
import random
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Realistic fingerprint data — rotated per-session for diversity
# ---------------------------------------------------------------------------

CHROME_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

FIREFOX_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1680, "height": 1050},
    {"width": 1280, "height": 720},
    {"width": 2560, "height": 1440},
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

# Realistic WebGL renderer strings per GPU vendor
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

# Realistic screen color depths
COLOR_DEPTHS = [24, 24, 24, 30, 32]

# ---------------------------------------------------------------------------
# Request interception — ad blocking + media blocking (inspired by Firecrawl)
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

# Resource types to block in crawl mode (saves bandwidth, speeds up loads).
# Images are NOT blocked — needed for screenshot rendering and lazy-load triggers.
CRAWL_BLOCKED_RESOURCE_TYPES = frozenset({"media", "font"})


async def _setup_route_blocking(
    context: BrowserContext, block_media: bool = False
):
    """Set up request interception on a context to block ads and optionally media.

    Args:
        context: Playwright BrowserContext to apply routes to.
        block_media: If True, also block video/audio/font resources (crawl mode).
    """

    async def _route_handler(route, request):
        url = request.url
        try:
            # Fast hostname extraction without urllib
            after_scheme = url.split("//", 1)[1]
            hostname = after_scheme.split("/", 1)[0].split(":")[0].lower()
        except (IndexError, ValueError):
            await route.continue_()
            return

        # Block ad-serving / tracking domains
        for domain in AD_SERVING_DOMAINS:
            if domain in hostname:
                await route.abort()
                return

        # Block heavy resource types in crawl mode
        if block_media and request.resource_type in CRAWL_BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return

        await route.continue_()

    await context.route("**/*", _route_handler)

# ---------------------------------------------------------------------------
# Chromium ULTRA-STEALTH script
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
delete navigator.__proto__.webdriver;

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
    // Also patch getExtension for WEBGL_debug_renderer_info
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
// Injects subtle random noise into every canvas toDataURL/toBlob call
// so each session produces a unique canvas fingerprint
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
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            const pixels = imageData.data;
            // Inject very subtle noise (±1 to a few random pixels)
            for (let i = 0; i < Math.min(pixels.length, 100); i += 4) {{
                if (nextRand() < 0.1) {{
                    pixels[i] = Math.max(0, Math.min(255, pixels[i] + (nextRand() < 0.5 ? 1 : -1)));
                }}
            }}
            ctx.putImageData(imageData, 0, 0);
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
// Each session produces a slightly different audio fingerprint
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
                // Add subtle gain variation
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
// Blocks WebRTC from revealing real IP address
// ============================================================

(function() {{
    // Override RTCPeerConnection to prevent IP leaks
    const origRTC = window.RTCPeerConnection || window.webkitRTCPeerConnection || window.mozRTCPeerConnection;
    if (origRTC) {{
        const newRTC = function(config) {{
            // Force relay-only ICE to prevent IP leak
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
    // window.devicePixelRatio
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
    // Also check document
    props.forEach(p => {{
        try {{ delete document[p]; }} catch(e) {{}}
    }});
}})();

// ============================================================
// LEVEL 13: CDP (Chrome DevTools Protocol) detection prevention
// Sites detect CDP by checking for Runtime.enable side effects
// ============================================================

(function() {{
    // Prevent Error.stack from revealing CDP
    const origPrepare = Error.prepareStackTrace;
    if (origPrepare) {{
        Error.prepareStackTrace = function(err, stack) {{
            // Filter out CDP-related frames
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
// LEVEL 17: Speech synthesis voices (Chrome has these)
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
// Make synthetic events indistinguishable from real ones
// ============================================================

(function() {{
    const origAddEvent = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, fn, options) {{
        if (type === 'keydown' || type === 'keyup' || type === 'keypress') {{
            const wrappedFn = function(e) {{
                // Ensure isTrusted looks real
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
// LEVEL 19: Document properties
// ============================================================

Object.defineProperty(document, 'hidden', {{ get: () => false }});
Object.defineProperty(document, 'visibilityState', {{ get: () => 'visible' }});

// ============================================================
// LEVEL 20: Performance.now() noise
// Prevent timing-based fingerprinting
// ============================================================

(function() {{
    const origNow = Performance.prototype.now;
    Performance.prototype.now = function() {{
        return origNow.call(this) + Math.random() * 0.1;
    }};
}})();
"""


def _build_firefox_stealth(hw_concurrency: int) -> str:
    """Build Firefox-specific stealth script."""
    return f"""
// Firefox stealth — lighter, targets Firefox-specific detection vectors

Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});

const ua = navigator.userAgent;
if (ua.includes('Win')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'Win32' }});
    Object.defineProperty(navigator, 'oscpu', {{ get: () => 'Windows NT 10.0; Win64; x64' }});
}} else if (ua.includes('Mac')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'MacIntel' }});
    Object.defineProperty(navigator, 'oscpu', {{ get: () => 'Intel Mac OS X 10.15' }});
}} else if (ua.includes('Linux')) {{
    Object.defineProperty(navigator, 'platform', {{ get: () => 'Linux x86_64' }});
    Object.defineProperty(navigator, 'oscpu', {{ get: () => 'Linux x86_64' }});
}}

Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw_concurrency} }});
Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => 0 }});

// Screen
try {{
    const w = window.innerWidth || 1920;
    const h = window.innerHeight || 1080;
    Object.defineProperty(screen, 'availWidth', {{ get: () => w }});
    Object.defineProperty(screen, 'availHeight', {{ get: () => h - 40 }});
}} catch(e) {{}}

// WebRTC IP leak prevention
(function() {{
    const origRTC = window.RTCPeerConnection || window.mozRTCPeerConnection;
    if (origRTC) {{
        const newRTC = function(config) {{
            if (config && config.iceServers) config.iceTransportPolicy = 'relay';
            return new origRTC(config);
        }};
        newRTC.prototype = origRTC.prototype;
        window.RTCPeerConnection = newRTC;
    }}
}})();

// Canvas noise
(function() {{
    const seed = {random.randint(1, 2**31)};
    let s = seed;
    function nextRand() {{ s = (s * 1664525 + 1013904223) & 0xFFFFFFFF; return (s >>> 0) / 0xFFFFFFFF; }}
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
        try {{
            const ctx = this.getContext('2d');
            if (ctx) {{
                const d = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < Math.min(d.data.length, 80); i += 4) {{
                    if (nextRand() < 0.1) d.data[i] = Math.max(0, Math.min(255, d.data[i] + (nextRand() < 0.5 ? 1 : -1)));
                }}
                ctx.putImageData(d, 0, 0);
            }}
        }} catch(e) {{}}
        return origToDataURL.apply(this, arguments);
    }};
}})();

// Hide automation
['domAutomation','domAutomationController','_selenium','__webdriver_script_fn',
 '__driver_evaluate','__webdriver_evaluate','__fxdriver_evaluate','_phantom','__nightmare'
].forEach(p => {{ try {{ delete window[p]; }} catch(e) {{}} }});

// Permissions
try {{
    const oq = window.Permissions?.prototype?.query;
    if (oq) {{
        window.Permissions.prototype.query = function(p) {{
            if (p?.name === 'notifications') return Promise.resolve({{ state: 'default' }});
            return oq.call(this, p);
        }};
    }}
}} catch(e) {{}}

Object.defineProperty(document, 'hidden', {{ get: () => false }});
Object.defineProperty(document, 'visibilityState', {{ get: () => 'visible' }});
"""


class BrowserPool:
    """Manages pools of Chromium and Firefox browsers for concurrent scraping.

    Chromium is the default. Firefox is used as fallback for hard-to-scrape
    sites because bot detection scripts primarily target Chrome/Chromium.
    Each page gets a unique fingerprint (WebGL, canvas seed, hardware, etc.).
    """

    _CHROMIUM_ARGS = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--window-size=1920,1080",
        "--start-maximized",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-hang-monitor",
        "--disable-prompt-on-repost",
        "--disable-background-networking",
        "--disable-sync",
        "--metrics-recording-only",
        "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
        "--enable-features=NetworkService,NetworkServiceInProcess",
        "--disable-web-security",
        "--allow-running-insecure-content",
        # Memory-saving flags for containerized environments
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--renderer-process-limit=2",
        "--js-flags=--max-old-space-size=256",
    ]

    def __init__(self):
        self._playwright = None
        self._chromium: Browser | None = None
        self._firefox: Browser | None = None
        self._chromium_semaphore: asyncio.Semaphore | None = None
        self._firefox_semaphore: asyncio.Semaphore | None = None
        self._initialized = False
        self._loop = None
        self._init_lock: asyncio.Lock | None = None
        # Cookie jar: domain -> list of cookies (persisted across page contexts)
        self._cookie_jar: dict[str, list[dict]] = {}

    def _get_init_lock(self) -> asyncio.Lock:
        """Get or create an asyncio.Lock bound to the current event loop."""
        current_loop = asyncio.get_running_loop()
        if self._init_lock is None or self._loop is not current_loop:
            self._init_lock = asyncio.Lock()
        return self._init_lock

    async def initialize(self):
        current_loop = asyncio.get_running_loop()

        if self._initialized and self._loop is current_loop:
            # Quick check: are the browsers still alive?
            if self._chromium and self._chromium.is_connected():
                return

        async with self._get_init_lock():
            # Double-check after acquiring lock
            if self._initialized and self._loop is current_loop:
                if self._chromium and self._chromium.is_connected():
                    return

            if self._initialized and self._loop is not current_loop:
                logger.debug("Event loop changed, reinitializing browser pool")
                self._force_kill_old_browsers()
                self._playwright = None
                self._chromium = None
                self._firefox = None
                self._initialized = False

            # Also reinitialize if browsers have crashed/disconnected
            if self._initialized and (
                not self._chromium or not self._chromium.is_connected()
            ):
                logger.warning(
                    "Chromium browser disconnected, reinitializing browser pool"
                )
                self._force_kill_old_browsers()
                self._playwright = None
                self._chromium = None
                self._firefox = None
                self._initialized = False

            self._loop = current_loop
            self._chromium_semaphore = asyncio.Semaphore(settings.CHROMIUM_POOL_SIZE)
            self._firefox_semaphore = asyncio.Semaphore(settings.FIREFOX_POOL_SIZE)
            self._playwright = await async_playwright().start()

            # Chromium with anti-detection flags
            self._chromium = await self._playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=self._CHROMIUM_ARGS,
            )

            # Firefox is lazy-initialized on first use to save memory
            self._firefox = None

            self._initialized = True
            logger.info(
                f"Browser pool initialized (chromium={settings.CHROMIUM_POOL_SIZE}, firefox={settings.FIREFOX_POOL_SIZE})"
            )

    async def _ensure_firefox(self):
        """Lazy-launch Firefox on first use."""
        if self._firefox and self._firefox.is_connected():
            return
        async with self._get_init_lock():
            if self._firefox and self._firefox.is_connected():
                return
            try:
                self._firefox = await self._playwright.firefox.launch(headless=True)
                logger.info("Firefox browser lazy-initialized")
            except Exception as e:
                logger.warning(f"Firefox launch failed: {e}")
                self._firefox = None

    async def _relaunch_browser(self, use_firefox: bool = False):
        """Relaunch a crashed browser. Must be called under _init_lock."""
        async with self._get_init_lock():
            if use_firefox:
                if self._firefox and self._firefox.is_connected():
                    return  # Already relaunched by another coroutine
                try:
                    self._firefox = await self._playwright.firefox.launch(headless=True)
                    logger.info("Firefox browser relaunched after crash")
                except Exception as e:
                    logger.warning(f"Firefox relaunch failed: {e}")
                    self._firefox = None
            else:
                if self._chromium and self._chromium.is_connected():
                    return  # Already relaunched by another coroutine
                try:
                    self._chromium = await self._playwright.chromium.launch(
                        headless=settings.BROWSER_HEADLESS,
                        args=self._CHROMIUM_ARGS,
                    )
                    logger.info("Chromium browser relaunched after crash")
                except Exception as e:
                    logger.error(f"Chromium relaunch failed, full reinit: {e}")
                    # Full reinit as last resort
                    self._initialized = False
                    await self.initialize()

    def _force_kill_old_browsers(self):
        """Synchronously kill old browser processes tied to a dead event loop."""
        import os
        import signal

        for browser in [self._chromium, self._firefox]:
            try:
                if browser and hasattr(browser, "_impl_obj"):
                    proc = getattr(browser._impl_obj, "_browser_process", None)
                    if proc and proc.pid:
                        os.kill(proc.pid, signal.SIGKILL)
            except Exception:
                pass
        try:
            if self._playwright and hasattr(self._playwright, "_impl_obj"):
                conn = getattr(self._playwright._impl_obj, "_connection", None)
                if conn:
                    transport = getattr(conn, "_transport", None)
                    if transport:
                        proc = getattr(transport, "_proc", None)
                        if proc:
                            proc.kill()
        except Exception:
            pass

    async def shutdown(self):
        if self._firefox:
            await self._firefox.close()
        if self._chromium:
            await self._chromium.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        self._loop = None
        logger.info("Browser pool shut down")

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for cookie jar."""
        try:
            from urllib.parse import urlparse

            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    async def _restore_cookies(self, context: BrowserContext, url: str):
        """Restore saved cookies for this domain."""
        domain = self._get_domain(url)
        if domain in self._cookie_jar:
            try:
                await context.add_cookies(self._cookie_jar[domain])
            except Exception:
                pass

    async def _save_cookies(self, context: BrowserContext, url: str):
        """Save cookies from this session for future reuse."""
        domain = self._get_domain(url)
        try:
            cookies = await context.cookies()
            if cookies:
                self._cookie_jar[domain] = cookies
        except Exception:
            pass

    def _is_browser_closed_error(self, exc: Exception) -> bool:
        """Check if an exception indicates the browser process has died."""
        msg = str(exc).lower()
        return any(
            phrase in msg
            for phrase in [
                "browser has been closed",
                "target page, context or browser has been closed",
                "browser.new_context",
                "connection closed",
                "browser closed",
            ]
        )

    @asynccontextmanager
    async def get_page(
        self,
        proxy: dict | None = None,
        stealth: bool = True,
        use_firefox: bool = False,
        target_url: str | None = None,
    ):
        """Get a browser page with unique fingerprint and full stealth.

        Args:
            proxy: Optional proxy dict for Playwright
            stealth: Whether to apply stealth patches
            use_firefox: Use Firefox instead of Chromium
            target_url: Target URL (used for cookie restoration)
        """
        await self.initialize()

        # Lazy-launch Firefox only when actually needed
        if use_firefox and (not self._firefox or not self._firefox.is_connected()):
            await self._ensure_firefox()

        from app.core.exceptions import BrowserPoolExhaustedError
        from app.core.metrics import active_browser_contexts

        is_firefox = use_firefox and self._firefox is not None
        semaphore = self._firefox_semaphore if is_firefox else self._chromium_semaphore

        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            browser_type = "Firefox" if is_firefox else "Chromium"
            raise BrowserPoolExhaustedError(
                f"No {browser_type} browser slots available after 30s"
            )
        try:  # replaces async with semaphore:
            active_browser_contexts.inc()
            try:
                # Resolve the browser reference, relaunching if it crashed
                browser = self._firefox if is_firefox else self._chromium
                if browser is None or not browser.is_connected():
                    logger.warning(
                        f"{'Firefox' if is_firefox else 'Chromium'} browser not connected, relaunching"
                    )
                    await self._relaunch_browser(use_firefox=is_firefox)
                    browser = self._firefox if is_firefox else self._chromium

                vp = random.choice(VIEWPORTS)
                tz = random.choice(TIMEZONES)

                # Generate unique session fingerprint
                hw_concurrency = random.choice([4, 8, 12, 16])
                device_mem = random.choice([4, 8, 16])
                webgl_vendor, webgl_renderer = random.choice(WEBGL_RENDERERS)
                color_depth = random.choice(COLOR_DEPTHS)

                if is_firefox:
                    ua = random.choice(FIREFOX_USER_AGENTS)
                    context_kwargs = dict(
                        user_agent=ua,
                        viewport=vp,
                        locale="en-US",
                        timezone_id=tz,
                        ignore_https_errors=True,
                        java_script_enabled=True,
                        has_touch=False,
                        is_mobile=False,
                        color_scheme="light",
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Accept-Encoding": "gzip, deflate, br",
                            "DNT": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                            "Upgrade-Insecure-Requests": "1",
                        },
                    )
                else:
                    ua = random.choice(CHROME_USER_AGENTS)
                    context_kwargs = dict(
                        user_agent=ua,
                        viewport=vp,
                        locale="en-US",
                        timezone_id=tz,
                        ignore_https_errors=True,
                        java_script_enabled=True,
                        has_touch=False,
                        is_mobile=False,
                        color_scheme="light",
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept-Encoding": "gzip, deflate, br",
                            "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
                            "Sec-Ch-Ua-Mobile": "?0",
                            "Sec-Ch-Ua-Platform": '"Windows"'
                            if "Win" in ua
                            else '"macOS"'
                            if "Mac" in ua
                            else '"Linux"',
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                            "Upgrade-Insecure-Requests": "1",
                        },
                    )

                if proxy:
                    context_kwargs["proxy"] = proxy

                # Try to create context, relaunch browser on failure
                try:
                    context: BrowserContext = await browser.new_context(
                        **context_kwargs
                    )
                except Exception as e:
                    if self._is_browser_closed_error(e):
                        logger.warning(
                            f"Browser closed during new_context, relaunching {'Firefox' if is_firefox else 'Chromium'}"
                        )
                        await self._relaunch_browser(use_firefox=is_firefox)
                        browser = self._firefox if is_firefox else self._chromium
                        if browser is None:
                            raise RuntimeError(
                                f"{'Firefox' if is_firefox else 'Chromium'} browser failed to relaunch"
                            ) from e
                        context = await browser.new_context(**context_kwargs)
                    else:
                        raise

                # Block ads (always) — saves bandwidth, speeds up loads
                await _setup_route_blocking(context, block_media=False)

                # Restore cookies from previous sessions for this domain
                if target_url:
                    await self._restore_cookies(context, target_url)

                if stealth:
                    if is_firefox:
                        script = _build_firefox_stealth(hw_concurrency)
                    else:
                        script = _build_chromium_stealth(
                            webgl_vendor,
                            webgl_renderer,
                            color_depth,
                            hw_concurrency,
                            device_mem,
                        )
                    await context.add_init_script(script)

                page: Page = await context.new_page()
                try:
                    yield page
                finally:
                    # Shield cleanup from cancellation to prevent resource leaks.
                    # CancelledError is BaseException in Python 3.9+, so bare
                    # `except Exception` would miss it and leak page/context.
                    try:
                        await asyncio.shield(
                            self._safe_cleanup_page(page, context, target_url)
                        )
                    except (asyncio.CancelledError, Exception):
                        # shield raises CancelledError if outer task was cancelled,
                        # but the shielded cleanup task keeps running in background
                        pass
            finally:
                active_browser_contexts.dec()
        finally:
            semaphore.release()

    async def _safe_cleanup_page(
        self, page: Page, context: BrowserContext, target_url: str | None
    ):
        """Cleanup page and context, safe against cancellation."""
        if target_url:
            try:
                await self._save_cookies(context, target_url)
            except BaseException:
                pass
        try:
            await page.close()
        except BaseException:
            pass
        try:
            await context.close()
        except BaseException:
            pass

    async def execute_actions(self, page: Page, actions: list[dict]) -> list[str]:
        """Execute a list of browser actions on the page.

        Supported actions:
        - click: Click element (supports button, click_count, modifiers)
        - type: Type text into element (character by character with delay)
        - fill: Fill input instantly (no typing delay)
        - wait: Wait for milliseconds
        - scroll: Scroll up/down by amount
        - screenshot: Take screenshot
        - hover: Hover over element
        - press: Press keyboard key (Enter, Tab, Escape, etc.)
        - select: Select dropdown option by value
        - fill_form: Fill multiple form fields at once
        - evaluate: Execute JavaScript code
        - go_back: Navigate back
        - go_forward: Navigate forward
        - wait_for_selector: Wait for element to appear
        - wait_for_navigation: Wait for page navigation
        - focus: Focus on element
        - clear: Clear input field
        """
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
                    screenshot = await page.screenshot(type="png")
                    screenshots.append(base64.b64encode(screenshot).decode())

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
                                await page.type(
                                    field_selector, field_value, delay=30, timeout=3000
                                )
                            except Exception:
                                pass
                    # Small delay after filling form
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
                logger.warning(f"Action '{action_type}' failed: {e}")

        return screenshots


class CrawlSession:
    """Persistent browser context held for an entire crawl job.

    Eliminates per-URL context creation overhead:
    - Stealth script injected once
    - Cookies accumulated across all pages
    - Semaphore slot held for duration (no re-acquisition)
    """

    def __init__(self, pool: BrowserPool, use_firefox: bool = False):
        self._pool = pool
        self._use_firefox = use_firefox
        self._context: BrowserContext | None = None
        self._semaphore_acquired = False
        self._cookies: list[dict] = []
        self._semaphore: asyncio.Semaphore | None = None
        self._recreate_lock: asyncio.Lock | None = None

    async def start(self, proxy: dict | None = None, target_url: str | None = None):
        """Acquire semaphore + create persistent context with stealth."""
        await self._pool.initialize()

        if self._use_firefox and (
            not self._pool._firefox or not self._pool._firefox.is_connected()
        ):
            await self._pool._ensure_firefox()

        from app.core.exceptions import BrowserPoolExhaustedError
        from app.core.metrics import active_browser_contexts

        is_firefox = self._use_firefox and self._pool._firefox is not None
        self._semaphore = (
            self._pool._firefox_semaphore
            if is_firefox
            else self._pool._chromium_semaphore
        )

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            browser_type = "Firefox" if is_firefox else "Chromium"
            raise BrowserPoolExhaustedError(
                f"No {browser_type} browser slots available after 30s"
            )
        self._semaphore_acquired = True
        active_browser_contexts.inc()

        browser = self._pool._firefox if is_firefox else self._pool._chromium
        if browser is None or not browser.is_connected():
            await self._pool._relaunch_browser(use_firefox=is_firefox)
            browser = self._pool._firefox if is_firefox else self._pool._chromium

        vp = random.choice(VIEWPORTS)
        tz = random.choice(TIMEZONES)
        hw_concurrency = random.choice([4, 8, 12, 16])
        device_mem = random.choice([4, 8, 16])
        webgl_vendor, webgl_renderer = random.choice(WEBGL_RENDERERS)
        color_depth = random.choice(COLOR_DEPTHS)

        if is_firefox:
            ua = random.choice(FIREFOX_USER_AGENTS)
            context_kwargs = dict(
                user_agent=ua,
                viewport=vp,
                locale="en-US",
                timezone_id=tz,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                color_scheme="light",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
        else:
            ua = random.choice(CHROME_USER_AGENTS)
            context_kwargs = dict(
                user_agent=ua,
                viewport=vp,
                locale="en-US",
                timezone_id=tz,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                color_scheme="light",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"'
                    if "Win" in ua
                    else '"macOS"'
                    if "Mac" in ua
                    else '"Linux"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

        if proxy:
            context_kwargs["proxy"] = proxy

        try:
            self._context = await browser.new_context(**context_kwargs)
        except Exception as e:
            if self._pool._is_browser_closed_error(e):
                await self._pool._relaunch_browser(use_firefox=is_firefox)
                browser = self._pool._firefox if is_firefox else self._pool._chromium
                if browser is None:
                    raise RuntimeError(
                        f"{'Firefox' if is_firefox else 'Chromium'} browser failed to relaunch"
                    ) from e
                self._context = await browser.new_context(**context_kwargs)
            else:
                raise

        # Block ads + heavy media (video/audio/fonts) for crawl speed
        await _setup_route_blocking(self._context, block_media=True)

        # Restore cookies from pool's cookie jar
        if target_url:
            await self._pool._restore_cookies(self._context, target_url)

        # Inject stealth script once on the context — applies to all pages
        if is_firefox:
            script = _build_firefox_stealth(hw_concurrency)
        else:
            script = _build_chromium_stealth(
                webgl_vendor,
                webgl_renderer,
                color_depth,
                hw_concurrency,
                device_mem,
            )
        await self._context.add_init_script(script)

        logger.info("CrawlSession started (persistent browser context)")

    async def new_page(self) -> Page:
        """Create a new page within the persistent context.

        Auto-recovers if the context was closed by a race cancellation or crash.
        Uses a lock so only one coroutine recreates the context at a time.
        """
        if not self._context:
            raise RuntimeError("CrawlSession not started")
        try:
            return await self._context.new_page()
        except Exception as e:
            # Context died (e.g. race cancellation TargetClosedError) — recreate it
            logger.warning(f"CrawlSession context dead, recreating: {e}")
            if self._recreate_lock is None:
                self._recreate_lock = asyncio.Lock()
            async with self._recreate_lock:
                # Double-check: another coroutine may have already recreated it
                try:
                    return await self._context.new_page()
                except Exception:
                    await self._recreate_context()
            return await self._context.new_page()

    async def _recreate_context(self):
        """Recreate the browser context after a crash, preserving cookies."""
        # Close the old dead context (ignore errors — it may already be dead)
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        is_firefox = self._use_firefox and self._pool._firefox is not None
        browser = self._pool._firefox if is_firefox else self._pool._chromium

        if browser is None or not browser.is_connected():
            await self._pool._relaunch_browser(use_firefox=is_firefox)
            browser = self._pool._firefox if is_firefox else self._pool._chromium

        vp = random.choice(VIEWPORTS)
        tz = random.choice(TIMEZONES)
        hw_concurrency = random.choice([4, 8, 12, 16])
        device_mem = random.choice([4, 8, 16])
        webgl_vendor, webgl_renderer = random.choice(WEBGL_RENDERERS)
        color_depth = random.choice(COLOR_DEPTHS)

        if is_firefox:
            ua = random.choice(FIREFOX_USER_AGENTS)
            context_kwargs = dict(
                user_agent=ua,
                viewport=vp,
                locale="en-US",
                timezone_id=tz,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                color_scheme="light",
            )
        else:
            ua = random.choice(CHROME_USER_AGENTS)
            context_kwargs = dict(
                user_agent=ua,
                viewport=vp,
                locale="en-US",
                timezone_id=tz,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                color_scheme="light",
            )

        self._context = await browser.new_context(**context_kwargs)

        # Re-apply route blocking after context recreation
        await _setup_route_blocking(self._context, block_media=True)

        # Re-inject stealth
        if is_firefox:
            script = _build_firefox_stealth(hw_concurrency)
        else:
            script = _build_chromium_stealth(
                webgl_vendor,
                webgl_renderer,
                color_depth,
                hw_concurrency,
                device_mem,
            )
        await self._context.add_init_script(script)

        # Restore accumulated cookies
        if self._cookies:
            try:
                await self._context.add_cookies(self._cookies)
            except Exception:
                pass

        logger.info("CrawlSession context recreated after crash")

    async def close_page(self, page: Page):
        """Close a page but keep the context alive. Saves cookies."""
        if self._context:
            try:
                cookies = await self._context.cookies()
                if cookies:
                    self._cookies = cookies
            except Exception:
                pass
        try:
            await page.close()
        except Exception:
            pass

    async def get_cookies_for_http(self) -> list[dict]:
        """Export cookies in a format usable by curl_cffi/httpx."""
        if self._context:
            try:
                self._cookies = await self._context.cookies()
            except Exception:
                pass
        return self._cookies

    async def stop(self):
        """Release resources: close context, release semaphore."""
        from app.core.metrics import active_browser_contexts

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._semaphore_acquired and self._semaphore:
            self._semaphore.release()
            self._semaphore_acquired = False
            active_browser_contexts.dec()

        logger.info("CrawlSession stopped")


# Global browser pool instance
browser_pool = BrowserPool()
