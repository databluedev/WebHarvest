import asyncio
import gzip
import logging
import random
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import httpx
from bs4 import BeautifulSoup

from app.schemas.map import MapRequest, LinkResult

logger = logging.getLogger(__name__)

# ── URL Normalization ────────────────────────────────────────────
# Tracking / analytics params that NEVER change page content.
# These are universally safe to strip on any website.
_TRACKING_PARAMS = frozenset({
    # Google / GA
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format", "utm_marketing_tactic",
    "_ga", "_gl", "_gid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    # Facebook / Meta
    "fbclid", "fb_action_ids", "fb_action_types", "fb_source", "fb_ref",
    # Microsoft / LinkedIn
    "msclkid", "li_fat_id",
    # Twitter / X
    "twclid",
    # HubSpot
    "_hsenc", "_hsmi", "hsa_cam", "hsa_grp", "hsa_mt", "hsa_src",
    "hsa_ad", "hsa_acc", "hsa_net", "hsa_ver", "hsa_la", "hsa_ol",
    "hsa_kw", "hsa_tgt",
    # Mailchimp
    "mc_cid", "mc_eid",
    # Adobe / Marketo
    "sc_campaign", "sc_channel", "sc_content", "sc_medium", "sc_outcome",
    "sc_geo", "sc_country",
    # Generic tracking / session
    "ref", "referer", "referrer", "source", "medium",
    "trk", "trkInfo", "trackingId",
    "intcmp", "icid", "int_cmp",
    "transaction_id",
    # Session identifiers
    "sid", "sessionid", "jsessionid", "phpsessid", "aspsessionid",
    # Misc
    "mkt_tok", "oly_anon_id", "oly_enc_id", "otc", "vero_id",
    "wickedid", "browser_id", "yclid", "ymclid",
})

# Paths that indicate non-content / auth-required pages
_JUNK_PATH_SEGMENTS = frozenset({
    "/wishlist", "/cart", "/checkout", "/login", "/signin", "/signup",
    "/register", "/account", "/my-account", "/profile", "/address",
    "/saved", "/oauth", "/callback", "/api/", "/graphql",
    "/password", "/forgot-password", "/reset-password",
    "/admin", "/wp-admin", "/wp-login",
})


def _normalize_url_for_map(url: str) -> str:
    """Strip tracking params and normalize a URL for deduplication."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {
            k: v for k, v in params.items()
            if k.lower() not in _TRACKING_PARAMS
        }
        if not cleaned:
            return parsed._replace(query="", fragment="").geturl()
        new_query = urlencode(cleaned, doseq=True)
        return parsed._replace(query=new_query, fragment="").geturl()
    except Exception:
        return url


def _is_junk_url(url: str) -> bool:
    """Return True if the URL is a non-content page (auth, cart, admin, etc.)."""
    try:
        path = urlparse(url).path.lower()
        return any(seg in path for seg in _JUNK_PATH_SEGMENTS)
    except Exception:
        return False

# Rotating headers for HTTP requests
_HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    },
]


async def _fetch_url(url: str, timeout: int = 15) -> tuple[str, int]:
    """Fetch a URL using curl_cffi (TLS impersonation) with httpx fallback."""
    # Try curl_cffi first
    try:
        from curl_cffi.requests import AsyncSession

        impersonate = random.choice(["chrome124", "chrome123", "chrome120"])
        async with AsyncSession(impersonate=impersonate) as session:
            resp = await session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers=random.choice(_HEADERS_LIST),
            )
            logger.debug(
                f"curl_cffi {url} -> {resp.status_code} ({len(resp.text)} chars)"
            )
            return resp.text, resp.status_code
    except Exception as e:
        logger.debug(f"curl_cffi failed for {url}: {e}")

    # Fallback to httpx
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=random.choice(_HEADERS_LIST),
            http2=True,
        ) as client:
            resp = await client.get(url)
            logger.debug(f"httpx {url} -> {resp.status_code} ({len(resp.text)} chars)")
            return resp.text, resp.status_code
    except Exception as e:
        logger.debug(f"httpx failed for {url}: {e}")

    return "", 0


async def _fetch_bytes(url: str, timeout: int = 15) -> tuple[bytes, int]:
    """Fetch a URL and return raw bytes (for gzip handling)."""
    try:
        from curl_cffi.requests import AsyncSession

        impersonate = random.choice(["chrome124", "chrome123", "chrome120"])
        async with AsyncSession(impersonate=impersonate) as session:
            resp = await session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers=random.choice(_HEADERS_LIST),
            )
            return resp.content, resp.status_code
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=random.choice(_HEADERS_LIST),
            http2=True,
        ) as client:
            resp = await client.get(url)
            return resp.content, resp.status_code
    except Exception:
        pass

    return b"", 0


async def _fetch_with_browser(url: str) -> str:
    """Fetch page content using browser with scrolling to load lazy content."""
    try:
        from app.services.browser import browser_pool

        async with browser_pool.get_page(target_url=url) as page:
            referrer = "https://www.google.com/"
            await page.goto(
                url, wait_until="domcontentloaded", timeout=45000, referer=referrer
            )
            # Wait for network to settle but don't block forever
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(random.randint(1000, 2500))

            # Scroll to bottom in increments to trigger lazy-loaded content
            for _ in range(3):
                await page.mouse.wheel(0, 3000)
                await page.wait_for_timeout(1000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass

            # Scroll back to top (some sites load nav elements on scroll-up)
            await page.mouse.wheel(0, -10000)
            await page.wait_for_timeout(500)

            return await page.content()
    except Exception as e:
        logger.warning(f"Browser fetch failed for {url}: {e}")
        return ""


async def _fetch_with_stealth_engine(url: str) -> str:
    """Fetch via stealth-engine sidecar. Returns HTML or empty string."""
    from app.config import settings

    if not settings.STEALTH_ENGINE_URL:
        return ""
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"{settings.STEALTH_ENGINE_URL}/scrape",
                json={"url": url, "timeout": 30000},
            )
            data = resp.json()
            if data.get("success"):
                return data.get("html", "")
    except Exception as e:
        logger.debug(f"Stealth engine failed for {url}: {e}")
    return ""


async def _fetch_guaranteed(url: str) -> str:
    """4-tier resilient fetch: curl_cffi → httpx → stealth engine → browser.

    Used for critical files like robots.txt where failure means losing all
    sitemap discovery. Each tier is tried in order until one succeeds.
    """
    # Tier 1 & 2: HTTP-level fetches (fast)
    text, status = await _fetch_url(url, timeout=15)
    if status == 200 and text and len(text.strip()) > 10:
        logger.info(f"Guaranteed fetch OK via HTTP for {url} ({len(text)} chars)")
        return text

    # Tier 3: Stealth engine (handles anti-bot)
    logger.info(f"HTTP fetch failed for {url}, trying stealth engine")
    html = await _fetch_with_stealth_engine(url)
    if html and len(html.strip()) > 10:
        # Stealth engine returns full HTML page — extract text content
        # For robots.txt, the raw text is inside the HTML body
        soup = BeautifulSoup(html, "lxml")
        body_text = soup.get_text(separator="\n")
        if body_text and ("user-agent" in body_text.lower() or "sitemap" in body_text.lower()):
            logger.info(f"Guaranteed fetch OK via stealth engine for {url}")
            return body_text
        # If stealth returned usable HTML but not a robots.txt text file,
        # still return the raw html for sitemap XML fetches
        if html.strip().startswith("<?xml") or "<urlset" in html or "<sitemapindex" in html:
            logger.info(f"Guaranteed fetch OK via stealth engine (XML) for {url}")
            return html

    # Tier 4: Full browser (nuclear option)
    logger.info(f"Stealth engine failed for {url}, trying browser")
    try:
        from app.services.browser import browser_pool

        async with browser_pool.get_page(target_url=url) as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            # For text files (robots.txt), content is inside <pre> or body
            content = await page.evaluate("() => document.body ? document.body.innerText : ''")
            if content and len(content.strip()) > 10:
                logger.info(f"Guaranteed fetch OK via browser for {url} ({len(content)} chars)")
                return content
            # Fallback: return full page HTML (for XML sitemaps rendered in browser)
            full_html = await page.content()
            if full_html:
                return full_html
    except Exception as e:
        logger.warning(f"Browser fetch also failed for {url}: {e}")

    logger.warning(f"All 4 tiers failed for {url}")
    return ""


async def _deep_discover_via_stealth_engine(url: str) -> tuple[str, list[str], str | None]:
    """Deep JS navigation discovery via stealth-engine.

    Returns (html, discovered_links, doc_framework).
    This is the god-tier strategy for documentation sites — it:
    1. Renders the page with full JS execution
    2. Auto-detects the doc framework (GitBook, Docusaurus, MkDocs, etc.)
    3. Waits for the sidebar/navigation to fully render
    4. Expands ALL collapsible nav sections (clicks toggles, opens details)
    5. Extracts every navigation link from the fully-rendered DOM
    """
    from app.config import settings

    if not settings.STEALTH_ENGINE_URL:
        return "", [], None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.STEALTH_ENGINE_URL}/scrape",
                json={
                    "url": url,
                    "timeout": 45000,
                    "discover_links": True,
                },
            )
            data = resp.json()
            if data.get("success"):
                html = data.get("html", "")
                links = data.get("discovered_links", [])
                framework = data.get("doc_framework")
                logger.info(
                    f"Deep discovery for {url}: framework={framework}, "
                    f"links={len(links)}, html={len(html)} chars"
                )
                return html, links, framework
    except Exception as e:
        logger.warning(f"Deep discovery via stealth engine failed for {url}: {e}")
    return "", [], None


async def _deep_discover_via_local_browser(url: str) -> tuple[str, list[str]]:
    """Deep JS navigation discovery via local browser (fallback when stealth engine unavailable).

    Uses the same sidebar expansion logic but via Playwright's evaluate().
    """
    try:
        from app.services.browser import browser_pool

        async with browser_pool.get_page(target_url=url) as page:
            referrer = "https://www.google.com/"
            await page.goto(
                url, wait_until="domcontentloaded", timeout=45000, referer=referrer
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(random.randint(2000, 3500))

            # Scroll to trigger lazy-loaded nav elements
            for _ in range(3):
                await page.mouse.wheel(0, 3000)
                await page.wait_for_timeout(800)
            await page.mouse.wheel(0, -10000)
            await page.wait_for_timeout(500)

            # Run the deep nav discovery JS (same as stealth engine)
            _DEEP_NAV_JS = """
            async () => {
                const result = { framework: null, links: [] };
                const frameworks = {
                    gitbook_modern: {
                        detect: ['[class*="gitbook"]', '.gitbook-root'],
                        nav: ['.gitbook-root nav a[href]', 'aside nav a[href]'],
                        expand: ['details:not([open]) > summary'],
                    },
                    gitbook_legacy: {
                        detect: ['.book-summary', '.book', '#book-search-input'],
                        nav: ['.book-summary a[href]', '.summary a[href]'],
                        expand: ['.articles .chapter-toggle'],
                    },
                    honkit: {
                        detect: ['.book.with-summary', 'meta[name="generator"][content*="HonKit"]'],
                        nav: ['.book-summary a[href]', '.summary a[href]', '.summary li a[href]'],
                        expand: ['details:not([open]) > summary'],
                    },
                    docusaurus: {
                        detect: ['#__docusaurus', '[class*="docusaurus"]'],
                        nav: ['.menu__link[href]', '.theme-doc-sidebar-menu a[href]'],
                        expand: ['.menu__list-item--collapsed > .menu__link--sublist'],
                    },
                    mkdocs_material: {
                        detect: ['.md-sidebar', 'meta[name="generator"][content*="mkdocs"]'],
                        nav: ['.md-nav a[href]', '.md-sidebar a[href]'],
                        expand: ['label.md-nav__link[for]'],
                    },
                    readthedocs: {
                        detect: ['.wy-nav-side', '.rst-content'],
                        nav: ['.wy-menu a[href]', '.toctree-l1 a[href]', '.toctree-l2 a[href]'],
                        expand: ['.toctree-expand'],
                    },
                    sphinx: {
                        detect: ['.sphinxsidebar', 'meta[name="generator"][content*="Sphinx"]'],
                        nav: ['.sphinxsidebarwrapper a[href]', '.toctree-wrapper a[href]'],
                        expand: [],
                    },
                    mdbook: {
                        detect: ['#sidebar', '.sidebar-scrollbox', 'meta[name="generator"][content*="mdBook"]'],
                        nav: ['.sidebar-scrollbox a[href]', '#sidebar a[href]'],
                        expand: ['details:not([open]) > summary'],
                    },
                };
                for (const [name, fw] of Object.entries(frameworks)) {
                    for (const sel of fw.detect) {
                        try { if (document.querySelector(sel)) { result.framework = name; break; } } catch {}
                    }
                    if (result.framework) break;
                }
                const fw = frameworks[result.framework];
                if (fw) {
                    const navSels = fw.nav.join(', ');
                    for (let i = 0; i < 10; i++) {
                        if (document.querySelectorAll(navSels).length >= 3) break;
                        await new Promise(r => setTimeout(r, 500));
                    }
                }
                for (let round = 0; round < 3; round++) {
                    document.querySelectorAll('details:not([open])').forEach(d => {
                        try { d.setAttribute('open', ''); d.open = true; } catch {}
                    });
                    if (fw) {
                        for (const sel of fw.expand) {
                            document.querySelectorAll(sel).forEach(el => { try { el.click(); } catch {} });
                        }
                    }
                    await new Promise(r => setTimeout(r, 500));
                }
                const linkSet = new Set();
                const origin = window.location.origin;
                function addLinks(sel) {
                    try {
                        document.querySelectorAll(sel).forEach(a => {
                            const href = a.href || a.getAttribute('href');
                            if (!href || href === '#' || href.startsWith('javascript:') || href.startsWith('mailto:')) return;
                            try { const u = new URL(href, origin); u.hash = ''; if (u.origin === origin) linkSet.add(u.href); } catch {}
                        });
                    } catch {}
                }
                if (fw) { for (const sel of fw.nav) addLinks(sel); }
                ['nav a[href]', '.sidebar a[href]', 'aside a[href]', '[role="navigation"] a[href]'].forEach(addLinks);
                if (linkSet.size < 10) {
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href; if (!href || href === '#' || href.startsWith('javascript:') || href.startsWith('mailto:')) return;
                        try { const u = new URL(href, origin); u.hash = ''; if (u.origin === origin) linkSet.add(u.href); } catch {}
                    });
                }
                result.links = Array.from(linkSet);
                return result;
            }
            """
            result = await page.evaluate(_DEEP_NAV_JS)
            links = result.get("links", [])
            html = await page.content()
            logger.info(
                f"Local browser deep discovery for {url}: "
                f"framework={result.get('framework')}, links={len(links)}"
            )
            return html, links
    except Exception as e:
        logger.warning(f"Local browser deep discovery failed for {url}: {e}")
        return "", []


async def map_website(request: MapRequest) -> list[LinkResult]:
    """
    Discover all URLs on a website using multiple strategies:
    1. Sitemap.xml parsing (with gzip, sitemap index, lastmod/priority)
    2. Quick crawl of homepage + linked pages (with anti-detection)
    3. Browser fallback for blocked sites
    4. Optional search/keyword filtering

    All URLs are normalized (tracking params stripped) and deduplicated.
    Junk URLs (login, cart, admin, etc.) are filtered out.
    """
    url = request.url
    all_links: dict[str, LinkResult] = {}

    def _add_link(link: LinkResult):
        """Add a link with normalization, dedup, and junk filtering."""
        clean_url = _normalize_url_for_map(link.url)
        if clean_url in all_links:
            return
        if _is_junk_url(clean_url):
            return
        all_links[clean_url] = LinkResult(
            url=clean_url,
            title=link.title,
            description=link.description,
            lastmod=getattr(link, "lastmod", None),
            priority=getattr(link, "priority", None),
        )

    # Strategy 1: Sitemap discovery (HIGHEST PRIORITY — canonical URLs)
    if request.use_sitemap:
        sitemap_links = await _parse_sitemaps(url)
        for link in sitemap_links:
            _add_link(link)
        if sitemap_links:
            logger.info(f"Sitemap strategy yielded {len(all_links)} clean URLs")

    # Strategy 2: Quick homepage crawl with anti-detection
    homepage_links = await _crawl_homepage(url, request.include_subdomains)
    for link in homepage_links:
        _add_link(link)

    # Strategy 3: Deep JS Navigation Discovery — the god-tier strategy for doc sites.
    # Renders the page with a real browser, detects the doc framework (GitBook,
    # Docusaurus, MkDocs, ReadTheDocs, etc.), waits for sidebar to render,
    # expands all collapsible nav trees, and extracts every navigation link.
    if len(all_links) < request.limit:
        logger.info(f"Running deep JS nav discovery for {url} (have {len(all_links)} links)")
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        if base_domain.startswith("www."):
            base_domain = base_domain[4:]

        # Try stealth engine first (best anti-detection + full discovery JS)
        html, discovered_links, doc_framework = await _deep_discover_via_stealth_engine(url)
        if not discovered_links:
            # Fallback to local browser
            html, discovered_links = await _deep_discover_via_local_browser(url)

        if discovered_links:
            logger.info(
                f"Deep discovery found {len(discovered_links)} links"
                f"{f' (framework: {doc_framework})' if doc_framework else ''}"
            )
            for link_url in discovered_links:
                parsed_link = urlparse(link_url)
                link_domain = parsed_link.netloc
                if link_domain.startswith("www."):
                    link_domain = link_domain[4:]
                # Filter by domain
                if request.include_subdomains:
                    base_parts = base_domain.split(".")
                    parsed_parts = link_domain.split(".")
                    if len(base_parts) >= 2 and len(parsed_parts) >= 2:
                        base_root = ".".join(base_parts[-2:])
                        parsed_root = ".".join(parsed_parts[-2:])
                        if base_root != parsed_root:
                            continue
                elif link_domain != base_domain:
                    continue
                _add_link(LinkResult(url=link_url, title=None, description=None))

        # Also extract standard links from the deep-discovery HTML
        if html and len(all_links) < request.limit:
            html_links = _extract_links_from_html(html, url, base_domain, request.include_subdomains)
            for link in html_links:
                _add_link(link)

    # Strategy 4: If we still got very few links, try basic browser fallback
    if len(all_links) < 5:
        logger.info(f"Few links found for {url}, trying browser fallback")
        browser_links = await _crawl_homepage_browser(url, request.include_subdomains)
        for link in browser_links:
            _add_link(link)

    # Strategy 5: Deep BFS crawl if we still have room under the limit
    if len(all_links) < request.limit:
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        seed_urls = [u for u in all_links if u != url][:20]  # seed with best URLs so far
        if seed_urls:
            remaining = request.limit - len(all_links)
            logger.info(
                f"Starting deep crawl for {url}: {len(seed_urls)} seeds, "
                f"need {remaining} more URLs"
            )
            deep_links = await _deep_crawl(
                seed_urls=seed_urls,
                base_domain=base_domain,
                include_subdomains=request.include_subdomains,
                limit=remaining,
            )
            for link in deep_links:
                _add_link(link)

    # Strategy 6: Filter by search term
    if request.search:
        search_lower = request.search.lower()
        filtered = {}
        for url_key, link in all_links.items():
            score = 0
            if search_lower in url_key.lower():
                score += 2
            if link.title and search_lower in link.title.lower():
                score += 3
            if link.description and search_lower in link.description.lower():
                score += 1
            if score > 0:
                filtered[url_key] = link
        all_links = filtered

    # Apply limit
    result = list(all_links.values())[: request.limit]
    return result


async def _parse_sitemaps(base_url: str) -> list[LinkResult]:
    """Discover and parse ALL sitemaps using a multi-strategy approach.

    Strategy:
        1. GUARANTEED fetch of robots.txt (4-tier cascade)
        2. Extract every Sitemap: directive from robots.txt
        3. If robots.txt had no sitemaps, try standard CMS fallback paths
        4. Check homepage HTML for <link rel="sitemap"> references
        5. Recursively follow sitemap indexes to discover all sub-sitemaps
        6. Deduplicate results
    """
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    # ── Step 1 & 2: robots.txt — the MOST important file ──────────
    sitemap_urls: list[str] = []

    robots_text = await _fetch_guaranteed(f"{domain}/robots.txt")
    if robots_text:
        for line in robots_text.splitlines():
            stripped = line.strip()
            # Case-insensitive match for "Sitemap:" directive
            if re.match(r"^sitemap\s*:", stripped, re.IGNORECASE):
                # Handle both "Sitemap: url" and "Sitemap:url" (no space)
                sm_url = re.split(r"^sitemap\s*:\s*", stripped, flags=re.IGNORECASE)[-1].strip()
                if sm_url and sm_url.startswith("http"):
                    sitemap_urls.append(sm_url)
        if sitemap_urls:
            logger.info(
                f"robots.txt discovery: found {len(sitemap_urls)} sitemap(s) "
                f"for {domain}: {sitemap_urls[:5]}"
            )
        else:
            logger.info(f"robots.txt fetched for {domain} but contained no Sitemap: directives")
    else:
        logger.warning(f"robots.txt fetch failed completely for {domain}")

    # ── Step 3: Standard CMS fallback paths (only if robots.txt had nothing) ──
    if not sitemap_urls:
        fallback_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap-index.xml",
            "/wp-sitemap.xml",
            "/sitemap.xml.gz",
            "/sitemap/sitemap.xml",
            "/sitemaps/sitemap.xml",
        ]
        sitemap_urls = [f"{domain}{p}" for p in fallback_paths]
        logger.info(f"No sitemaps from robots.txt, trying {len(sitemap_urls)} standard paths")

    # ── Step 4: Check homepage HTML for <link rel="sitemap"> ──────
    try:
        homepage_text, homepage_status = await _fetch_url(base_url, timeout=15)
        if homepage_status == 200 and homepage_text:
            soup = BeautifulSoup(homepage_text, "lxml")
            for link_tag in soup.find_all("link", rel=True):
                rels = [r.lower() for r in link_tag.get("rel", [])]
                if "sitemap" in rels:
                    href = link_tag.get("href", "").strip()
                    if href:
                        abs_href = urljoin(base_url, href)
                        if abs_href not in sitemap_urls:
                            sitemap_urls.append(abs_href)
                            logger.info(f"Found sitemap in HTML <link>: {abs_href}")
    except Exception as e:
        logger.debug(f"Homepage <link> sitemap check failed: {e}")

    # ── Step 5: Fetch and recursively parse all discovered sitemaps ──
    all_links: list[LinkResult] = []
    visited_sitemaps: set[str] = set()

    async def _recursive_parse(url: str, depth: int = 0):
        """Recursively fetch and parse a sitemap, following indexes."""
        if url in visited_sitemaps or depth > 3:
            return
        visited_sitemaps.add(url)

        xml_text = await _fetch_sitemap_content(url)
        if not xml_text:
            return

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"XML parse error for {url}: {e}")
            return

        ns = {
            "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
            "image": "http://www.google.com/schemas/sitemap-image/1.1",
        }

        # Check if it's a sitemap index (contains <sitemap><loc> entries)
        index_entries = root.findall(".//sm:sitemap/sm:loc", ns)
        # Also handle sitemaps without namespace prefix
        if not index_entries:
            index_entries = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        # Also try no-namespace (some sites serve sitemaps without xmlns)
        if not index_entries:
            index_entries = root.findall(".//sitemap/loc")

        if index_entries:
            logger.info(f"Sitemap index at {url}: {len(index_entries)} sub-sitemaps (depth={depth})")
            for entry in index_entries[:500]:
                if entry.text:
                    sub_url = entry.text.strip()
                    await _recursive_parse(sub_url, depth + 1)
        else:
            # It's a URL set — extract all URLs
            sub_links = _parse_single_sitemap_xml(root, ns)
            if sub_links:
                logger.info(f"Sitemap {url}: extracted {len(sub_links)} URLs")
                all_links.extend(sub_links)

    # Deduplicate sitemap URLs before fetching
    seen_sitemap_urls = set()
    unique_sitemap_urls = []
    for sm_url in sitemap_urls:
        if sm_url not in seen_sitemap_urls:
            seen_sitemap_urls.add(sm_url)
            unique_sitemap_urls.append(sm_url)

    for sm_url in unique_sitemap_urls:
        await _recursive_parse(sm_url)

    # ── Step 6: Deduplicate results ───────────────────────────────
    seen_urls: set[str] = set()
    deduped: list[LinkResult] = []
    for link in all_links:
        normalized = _normalize_url_for_map(link.url)
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            deduped.append(LinkResult(
                url=normalized,
                title=link.title,
                description=link.description,
                lastmod=link.lastmod,
                priority=link.priority,
            ))

    logger.info(
        f"Sitemap discovery complete for {domain}: "
        f"{len(all_links)} raw → {len(deduped)} deduplicated URLs "
        f"from {len(visited_sitemaps)} sitemaps"
    )
    return deduped


async def _fetch_sitemap_content(url: str) -> str | None:
    """Fetch sitemap content with gzip support and stealth fallback.

    Tries HTTP first (fast), falls back to stealth/browser for blocked sites.
    """
    if url.endswith(".gz"):
        # Fetch as bytes and decompress
        raw_bytes, status = await _fetch_bytes(url, timeout=20)
        if status != 200 or not raw_bytes:
            return None
        try:
            decompressed = gzip.decompress(raw_bytes)
            return decompressed.decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"Failed to decompress gzipped sitemap {url}: {e}")
            return None

    # Try HTTP first (fast path — most sitemap XML files are not anti-bot protected)
    text, status = await _fetch_url(url, timeout=15)
    if status == 200 and text:
        # Sanity check: does it look like XML?
        stripped = text.strip()
        if stripped.startswith("<?xml") or stripped.startswith("<urlset") or stripped.startswith("<sitemapindex"):
            return text
        # Some servers return HTML error pages with 200 status — reject those
        if "<html" in stripped[:200].lower():
            logger.debug(f"Sitemap {url} returned HTML instead of XML, trying stealth")
        else:
            return text

    # Stealth fallback for anti-bot protected sitemap files
    logger.debug(f"HTTP failed for sitemap {url} (status={status}), trying stealth")
    stealth_text = await _fetch_with_stealth_engine(url)
    if stealth_text:
        # Stealth engine wraps content in HTML — extract the XML
        if "<?xml" in stealth_text or "<urlset" in stealth_text or "<sitemapindex" in stealth_text:
            # Try to extract raw XML from any HTML wrapper
            soup = BeautifulSoup(stealth_text, "lxml")
            # The XML might be inside a <pre> tag
            pre = soup.find("pre")
            if pre:
                return pre.get_text()
            # Or it might be the full content
            body_text = soup.get_text()
            if "<?xml" in body_text or "<urlset" in body_text:
                return body_text
            return stealth_text

    return None


def _parse_single_sitemap_xml(root: ET.Element, ns: dict) -> list[LinkResult]:
    """Extract URLs from a sitemap XML element with lastmod, priority, and image support."""
    links = []
    # Try with namespace first, then without (some sites skip xmlns)
    url_elements = root.findall(".//sm:url", ns)
    if not url_elements:
        url_elements = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url")
    if not url_elements:
        url_elements = root.findall(".//url")

    for url_el in url_elements:
        loc = url_el.find("sm:loc", ns)
        if loc is None:
            loc = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc is None:
            loc = url_el.find("loc")
        if loc is None or not loc.text:
            continue

        url = loc.text.strip()

        # Parse optional fields
        lastmod_el = url_el.find("sm:lastmod", ns)
        lastmod = (
            lastmod_el.text.strip()
            if lastmod_el is not None and lastmod_el.text
            else None
        )

        priority_el = url_el.find("sm:priority", ns)
        priority = None
        if priority_el is not None and priority_el.text:
            try:
                priority = float(priority_el.text.strip())
            except ValueError:
                pass

        changefreq_el = url_el.find("sm:changefreq", ns)
        changefreq = (
            changefreq_el.text.strip()
            if changefreq_el is not None and changefreq_el.text
            else None
        )

        # Parse image sitemap entries
        image_urls = []
        for img_el in url_el.findall("image:image/image:loc", ns):
            if img_el.text:
                image_urls.append(img_el.text.strip())

        # Build description from metadata
        desc_parts = []
        if lastmod:
            desc_parts.append(f"Updated: {lastmod}")
        if changefreq:
            desc_parts.append(f"Freq: {changefreq}")
        if priority is not None:
            desc_parts.append(f"Priority: {priority}")
        if image_urls:
            desc_parts.append(f"{len(image_urls)} image(s)")

        description = " | ".join(desc_parts) if desc_parts else None

        links.append(
            LinkResult(
                url=url,
                title=None,
                description=description,
                lastmod=lastmod,
                priority=priority,
            )
        )

    return links


async def _crawl_homepage(base_url: str, include_subdomains: bool) -> list[LinkResult]:
    """Quick crawl of homepage using curl_cffi for anti-detection."""
    links = []
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    if base_domain.startswith("www."):
        base_domain = base_domain[4:]

    try:
        text, status = await _fetch_url(base_url, timeout=20)
        if not text:
            return links

        links = _extract_links_from_html(
            text, base_url, base_domain, include_subdomains
        )
        logger.info(
            f"Homepage crawl for {base_url}: status={status}, links={len(links)}"
        )

    except Exception as e:
        logger.warning(f"Homepage crawl failed for {base_url}: {e}")

    return links


async def _crawl_homepage_browser(
    base_url: str, include_subdomains: bool
) -> list[LinkResult]:
    """Crawl homepage using stealth-engine (preferred) or local browser with scrolling."""
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    try:
        # Try stealth-engine first, fall back to local browser
        html = await _fetch_with_stealth_engine(base_url)
        if not html:
            html = await _fetch_with_browser(base_url)
        if not html:
            return []

        return _extract_links_from_html(html, base_url, base_domain, include_subdomains)

    except Exception as e:
        logger.warning(f"Browser homepage crawl failed for {base_url}: {e}")
        return []


async def _fetch_page_html(url: str) -> str:
    """Fetch a page's HTML using stealth-engine → browser → HTTP cascade."""
    # 1. Stealth engine (best anti-detection)
    html = await _fetch_with_stealth_engine(url)
    if html:
        return html
    # 2. Local browser with scrolling
    html = await _fetch_with_browser(url)
    if html:
        return html
    # 3. HTTP fallback
    text, status = await _fetch_url(url, timeout=15)
    if status and text:
        return text
    return ""


async def _deep_crawl(
    seed_urls: list[str],
    base_domain: str,
    include_subdomains: bool,
    limit: int,
    max_depth: int = 2,
) -> list[LinkResult]:
    """BFS crawl following internal links up to max_depth to discover more URLs."""
    discovered: dict[str, LinkResult] = {}
    visited: set[str] = set()
    sem = asyncio.Semaphore(5)

    # Normalize base_domain for comparison
    clean_base = base_domain
    if clean_base.startswith("www."):
        clean_base = clean_base[4:]

    # Initialize queue with seeds: (url, depth)
    queue: list[tuple[str, int]] = [(u, 1) for u in seed_urls if u not in visited]

    async def _process_url(url: str, depth: int) -> list[tuple[str, int]]:
        """Fetch a URL, extract links, return new (url, depth) pairs to enqueue."""
        async with sem:
            html = await _fetch_page_html(url)
        if not html:
            return []
        links = _extract_links_from_html(html, url, base_domain, include_subdomains)
        new_pairs = []
        for link in links:
            if link.url not in discovered and link.url not in visited:
                discovered[link.url] = link
                if len(discovered) >= limit:
                    return new_pairs
                if depth < max_depth:
                    new_pairs.append((link.url, depth + 1))
        return new_pairs

    # BFS by depth level
    while queue and len(discovered) < limit:
        # Deduplicate and filter already-visited
        batch = []
        for url, depth in queue:
            if url not in visited:
                visited.add(url)
                batch.append((url, depth))

        if not batch:
            break

        # Process current level in parallel (bounded by semaphore)
        tasks = [_process_url(url, depth) for url, depth in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        queue = []
        for result in results:
            if isinstance(result, list):
                queue.extend(result)
            if len(discovered) >= limit:
                break

    logger.info(f"Deep crawl discovered {len(discovered)} URLs (limit={limit})")
    return list(discovered.values())[:limit]


def _extract_links_from_html(
    html: str, base_url: str, base_domain: str, include_subdomains: bool
) -> list[LinkResult]:
    """Extract all links from HTML content."""
    links = []
    soup = BeautifulSoup(html, "lxml")

    # Get page title and description for context
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)

        # Only http/https
        if parsed.scheme not in ("http", "https"):
            continue

        # Filter by domain
        if not include_subdomains and parsed.netloc != base_domain:
            continue
        if include_subdomains:
            # Allow subdomains of the same root domain
            base_parts = base_domain.split(".")
            parsed_parts = parsed.netloc.split(".")
            if len(base_parts) >= 2 and len(parsed_parts) >= 2:
                base_root = ".".join(base_parts[-2:])
                parsed_root = ".".join(parsed_parts[-2:])
                if base_root != parsed_root:
                    continue

        # Clean URL — preserve SPA-style hash routes (#!/... or #/...)
        # but strip plain anchor fragments (#section-name)
        frag = parsed.fragment
        if frag and (frag.startswith("/") or frag.startswith("!/")):
            clean_url = parsed.geturl()  # keep SPA route fragment
        else:
            clean_url = parsed._replace(fragment="").geturl()

        title = a_tag.get_text(strip=True) or None

        # Get description from nearby text or parent
        description = None
        parent = a_tag.parent
        if parent:
            sibling_text = parent.get_text(strip=True)
            if sibling_text and sibling_text != title and len(sibling_text) < 200:
                description = sibling_text

        links.append(LinkResult(url=clean_url, title=title, description=description))

    return links
