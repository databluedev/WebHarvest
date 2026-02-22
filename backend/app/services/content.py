import json
import logging
import math
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Go HTML-to-Markdown sidecar client (sync — runs inside ThreadPoolExecutor)
# ---------------------------------------------------------------------------

_sidecar_client: httpx.Client | None = None


def _get_sidecar_client() -> httpx.Client | None:
    """Return a reusable sync httpx client for the Go sidecar, or None if disabled."""
    global _sidecar_client
    if not settings.GO_HTML_TO_MD_URL:
        return None
    if _sidecar_client is None or _sidecar_client.is_closed:
        _sidecar_client = httpx.Client(
            base_url=settings.GO_HTML_TO_MD_URL,
            timeout=30.0,
        )
    return _sidecar_client


def _convert_via_sidecar(html: str) -> str | None:
    """Convert HTML to markdown via the Go sidecar. Returns None on failure."""
    client = _get_sidecar_client()
    if client is None:
        return None
    try:
        resp = client.post("/convert", json={"html": html})
        if resp.status_code == 200:
            return resp.json().get("markdown", None)
        logger.debug(f"Go sidecar returned status {resp.status_code}")
    except Exception as e:
        logger.debug(f"Go sidecar conversion failed: {e}")
    return None

# Tags that are always junk — can't be rendered as meaningful markdown.
# NOTE: "noscript" is intentionally KEPT — it contains fallback content
# for lazy-loaded images and JS-disabled browsers.
JUNK_TAGS = {
    "script",
    "style",
    "iframe",
    "svg",
    "path",
    "meta",
    "link",
    "video",
    "audio",
    "canvas",
    "object",
    "embed",
    "source",
    "track",
    "dialog",
    "template",
    "select",
    "option",
    "datalist",
}

# ---------------------------------------------------------------------------
# Hard junk: ALWAYS removed regardless of only_main_content setting.
# These are never useful page content under any circumstances.
# ---------------------------------------------------------------------------
HARD_JUNK_SELECTORS = [
    # Cookie/consent/GDPR banners
    ".cookie-banner",
    ".cookie-popup",
    "#cookie-consent",
    ".gdpr-banner",
    ".cookie-notice",
    "#cookie-notice",
    ".consent-banner",
    "[class*='cookie-consent']",
    "[class*='cookie-banner']",
    "[class*='cookie-notice']",
    "[class*='consent-']",
    # Modals/popups/overlays
    "[role='dialog']",
    "[role='alertdialog']",
    ".modal",
    ".popup",
    ".overlay-content",
    "[class*='-modal']",
    "[class*='modal-']",
    # Video/media player UI (controls, settings, captions)
    ".vjs-control-bar",
    ".vjs-menu",
    ".vjs-text-track-settings",
    ".vjs-modal-dialog",
    "[class*='caption-window']",
    "[class*='caption-settings']",
    "[class*='player-controls']",
    # Accessibility/screen-reader-only (not visible content)
    ".skip-link",
    ".skip-nav",
    ".sr-only",
    ".visually-hidden",
    ".screen-reader-only",
    "[class*='skip-to']",
    # Ads
    ".sidebar-ad",
    "[class*='ad-slot']",
    "[class*='advertisement']",
    # Chat widgets
    "[class*='chat-widget']",
    "[class*='live-chat']",
    "#hubspot-messages-iframe-container",
]

# ---------------------------------------------------------------------------
# Soft boilerplate: ONLY removed when only_main_content=True.
# These contain structural content that may be valuable in full-page mode.
# ---------------------------------------------------------------------------
SOFT_BOILERPLATE_SELECTORS = [
    # Navigation
    "nav",
    "[role='navigation']",
    # Social sharing
    ".share-buttons",
    ".social-share",
    "[class*='social-links']",
    "[class*='share-bar']",
    "[class*='share-buttons']",
    # Search forms
    "[role='search']",
    # Announcement/promo bars
    ".announcement-bar",
    ".promo-bar",
    ".top-banner",
    ".alert-bar",
    # Newsletter signup
    "[class*='newsletter']",
    "[class*='subscribe-form']",
    "[class*='email-signup']",
    # Back to top
    ".back-to-top",
    "#back-to-top",
    "[class*='scroll-to-top']",
    # Breadcrumbs
    ".breadcrumb",
    ".breadcrumbs",
    "[class*='breadcrumb']",
    # Pagination
    ".pagination",
    ".pager",
    "[class*='pagination']",
]

# Combined list for only_main_content=True (backward compat)
BOILERPLATE_SELECTORS = HARD_JUNK_SELECTORS + SOFT_BOILERPLATE_SELECTORS

# Selectors for elements that should ALWAYS be kept
PRESERVE_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".content",
    "#content",
    ".post",
    ".entry",
    ".product",
    ".product-detail",
]

# ---------------------------------------------------------------------------
# Documentation framework content selectors — used for precise extraction
# on doc sites where generic <main>/<article> selectors may miss content
# or include sidebar/nav boilerplate.
# ---------------------------------------------------------------------------

# Maps framework → (main_content_selectors, extra_boilerplate_to_remove)
DOC_FRAMEWORK_EXTRACTION: dict[str, tuple[list[str], list[str]]] = {
    "gitbook": (
        [".gitbook-root main", ".page-inner .markdown-section", ".page-inner section", ".page-wrapper .page-inner"],
        [".gitbook-root nav", ".gitbook-root aside", ".book-summary", ".book-header", ".page-footer"],
    ),
    "honkit": (
        [".book-body .page-inner", ".book-body .markdown-section", ".body-inner .page-inner"],
        [".book-summary", ".book-header", ".book-footer", ".page-footer", ".navigation"],
    ),
    "docusaurus": (
        [".theme-doc-markdown", "article[class*='docItemCol']", ".docMainContainer article", "main article"],
        [".theme-doc-sidebar-container", ".theme-doc-footer", ".pagination-nav", ".docSidebarContainer", "[class*='tableOfContents']"],
    ),
    "mkdocs": (
        [".md-content article", ".md-content", "[data-md-component='content'] article"],
        [".md-sidebar", ".md-header", ".md-footer", ".md-tabs", "[data-md-component='sidebar']"],
    ),
    "readthedocs": (
        [".rst-content", ".wy-nav-content .section", ".document .section"],
        [".wy-nav-side", ".wy-breadcrumbs", ".wy-nav-top", ".rst-footer-buttons", ".footer"],
    ),
    "sphinx": (
        [".body", ".document .body", ".documentwrapper .body"],
        [".sphinxsidebar", ".related", ".footer", ".clearer"],
    ),
    "vuepress": (
        [".theme-default-content", ".page .content__default", ".page main"],
        [".sidebar", ".navbar", ".page-edit", ".page-nav"],
    ),
    "vitepress": (
        [".VPDoc .vp-doc", ".VPContent main", ".vp-doc"],
        [".VPSidebar", ".VPNav", ".VPFooter", ".VPDocFooter", "[class*='aside']"],
    ),
    "nextra": (
        ["article.nextra-content", "main article", ".nextra-body main article"],
        [".nextra-sidebar-container", "nav.nextra-sidebar", ".nextra-toc"],
    ),
    "hugo": (
        [".book-page article", "main article", ".prose", ".markdown"],
        [".book-menu", ".book-footer", "#TableOfContents"],
    ),
    "mdbook": (
        ["#content main", "#content .content", "main"],
        ["#sidebar", ".sidebar-scrollbox", "#menu-bar"],
    ),
    "starlight": (
        ["main article", "[data-pagefind-body]", "main [data-has-sidebar] article"],
        ["aside nav", "header", ".pagination-links"],
    ),
    "mintlify": (
        ["main article", "article.prose"],
        ["nav", "aside", "footer"],
    ),
}


class WebHarvestConverter(MarkdownConverter):
    """Custom markdown converter that preserves links, structure, and all content."""

    def convert_a(self, el, text, *args, **kwargs):
        """Preserve links with their text and href."""
        href = el.get("href", "")
        title = el.get("title", "")
        text = (text or "").strip()

        if not text or not href:
            return text or ""

        # Skip anchor-only links
        if href.startswith("#") and len(href) <= 1:
            return text

        if title:
            return f'[{text}]({href} "{title}")'
        return f"[{text}]({href})"

    def convert_img(self, el, text, *args, **kwargs):
        """Convert images to markdown with alt text."""
        alt = el.get("alt", "")
        src = el.get("src", "")
        if not src:
            return ""
        if alt:
            return f"![{alt}]({src})"
        return f"![]({src})"

    def convert_pre(self, el, text, *args, **kwargs):
        """Preserve code blocks."""
        code = el.find("code")
        lang = ""
        if code:
            classes = code.get("class", [])
            for cls in classes:
                if cls.startswith("language-"):
                    lang = cls[9:]
                    break
            text = code.get_text()
        else:
            text = el.get_text()
        return f"\n```{lang}\n{text}\n```\n"

    def convert_dl(self, el, text, *args, **kwargs):
        """Preserve definition lists as structured markdown."""
        return f"\n{text}\n"

    def convert_dt(self, el, text, *args, **kwargs):
        """Definition term — render as bold."""
        return f"\n**{(text or '').strip()}**\n"

    def convert_dd(self, el, text, *args, **kwargs):
        """Definition description — render indented under the term."""
        return f": {(text or '').strip()}\n"

    def convert_time(self, el, text, *args, **kwargs):
        """Preserve <time> datetime attribute alongside visible text."""
        dt = el.get("datetime", "")
        display = (text or "").strip()
        if dt and dt != display:
            return f"{display} ({dt})"
        return display

    def convert_details(self, el, text, *args, **kwargs):
        """Preserve expandable <details> sections."""
        return f"\n{text}\n"

    def convert_summary(self, el, text, *args, **kwargs):
        """Render <summary> as a bold header for the details block."""
        return f"\n**{(text or '').strip()}**\n"


def _is_inside_main_content(el: Tag) -> bool:
    """Check if element is inside a main content container (main, article, etc.)."""
    for parent in el.parents:
        if not isinstance(parent, Tag):
            continue
        tag = parent.name
        if tag in ("main", "article"):
            return True
        role = parent.get("role", "")
        if role == "main":
            return True
        el_id = parent.get("id", "")
        if el_id in ("content", "main-content"):
            return True
        classes = parent.get("class", [])
        if any(
            c
            in ("content", "main-content", "post", "entry", "product", "product-detail")
            for c in classes
        ):
            return True
    return False


def _clean_soup(html: str) -> BeautifulSoup:
    """Parse HTML once and clean junk/boilerplate. Returns the cleaned soup."""
    soup = BeautifulSoup(html, "lxml")

    # Remove definite junk tags
    for tag in soup.find_all(list(JUNK_TAGS)):
        tag.decompose()

    # Remove ALL boilerplate — no text-length mercy
    for selector in BOILERPLATE_SELECTORS:
        try:
            for el in soup.select(selector):
                if _is_inside_main_content(el):
                    continue
                el.decompose()
        except Exception:
            pass

    # Remove hidden/invisible elements
    _remove_hidden_elements(soup)

    # Remove form elements only if they have very little text (search bars, dropdowns)
    for form in soup.find_all("form"):
        form_text = form.get_text(strip=True)
        if len(form_text) < 1000:
            form.decompose()

    return soup


def _extract_main_tag(html: str, url: str = "") -> Tag | BeautifulSoup:
    """
    Internal extraction that returns a BS4 Tag (not a serialized string).
    Avoids redundant re-parsing by working with soup objects throughout.
    """
    soup = _clean_soup(html)

    # Try to find main content container
    main_content = _find_main_container(soup)

    # Aggressive body extraction as fallback
    if not main_content:
        main_content = _smart_body_extract(soup)

    # Get text length directly from the tag — no re-parse needed
    bs4_text_len = len(main_content.get_text(strip=True)) if main_content else 0

    # Skip trafilatura when BS4 found sufficient content (saves 150-250ms)
    if bs4_text_len > 500:
        logger.debug(f"BS4 extraction sufficient ({bs4_text_len} chars), skipping trafilatura")
        return main_content or soup.body or soup

    # Only call trafilatura for weak BS4 results
    traf_tag = None
    try:
        import trafilatura

        traf_result = trafilatura.extract(
            html,
            include_links=True,
            include_images=True,
            include_tables=True,
            favor_recall=True,
            url=url,
            output_format="html",
        )
        if traf_result:
            traf_tag = BeautifulSoup(traf_result, "lxml")
    except Exception as e:
        logger.debug(f"Trafilatura extraction failed: {e}")

    traf_text_len = len(traf_tag.get_text(strip=True)) if traf_tag else 0

    # Pick whichever captured MORE content
    if bs4_text_len > traf_text_len * 1.2:
        logger.debug(
            f"Using BS4 extraction ({bs4_text_len} chars > trafilatura {traf_text_len} chars)"
        )
        return main_content or soup.body or soup
    elif traf_text_len > 100:
        logger.debug(f"Using trafilatura extraction ({traf_text_len} chars)")
        return traf_tag
    else:
        return main_content or soup.body or soup


def extract_main_content(html: str, url: str = "") -> str:
    """
    Multi-pass content extraction that produces clean, high-quality output.
    Returns cleaned HTML string.
    """
    tag = _extract_main_tag(html, url)
    return str(tag) if tag else ""


def _remove_hidden_elements(soup: BeautifulSoup) -> None:
    """Remove elements that are hidden/invisible via inline styles or attributes.

    Collects elements before iterating to avoid tree mutation issues where
    decomposing one element can set sibling attrs to None in BeautifulSoup.
    """
    # Collect elements first to avoid iterator invalidation during decompose
    styled = list(soup.find_all(style=True))
    for el in styled:
        if not hasattr(el, "attrs") or not isinstance(el.attrs, dict):
            continue
        style = el.attrs.get("style", "")
        if not style:
            continue
        if "display:none" in style.replace(" ", "") or "display: none" in style:
            el.decompose()
            continue
        if (
            "visibility:hidden" in style.replace(" ", "")
            or "visibility: hidden" in style
        ):
            el.decompose()

    # Elements with hidden attribute
    hidden = list(soup.find_all(attrs={"hidden": True}))
    for el in hidden:
        try:
            el.decompose()
        except Exception:
            pass

    # aria-hidden elements (usually decorative) — only remove truly empty ones
    aria_hidden = list(soup.find_all(attrs={"aria-hidden": "true"}))
    for el in aria_hidden:
        try:
            if len(el.get_text(strip=True)) < 30:
                el.decompose()
        except Exception:
            pass


def _detect_doc_framework(soup: BeautifulSoup) -> str | None:
    """Detect documentation framework from parsed HTML."""
    _detect_map = {
        "gitbook": ['[class*="gitbook"]', ".gitbook-root", ".book-summary"],
        "honkit": [".book.with-summary", ".book-summary", ".book-header .btn-group"],
        "docusaurus": ["#__docusaurus", '[class*="docusaurus"]'],
        "mkdocs": [".md-sidebar", ".md-content", '[data-md-component="sidebar"]'],
        "readthedocs": [".wy-nav-side", ".rst-content"],
        "sphinx": [".sphinxsidebar", ".sphinxsidebarwrapper"],
        "vuepress": [".theme-default-content", ".theme-container"],
        "vitepress": [".VPSidebar", ".VPDoc", "#VPContent"],
        "nextra": ['[class*="nextra"]', ".nextra-sidebar-container"],
        "hugo": [".book-menu", ".book-page"],
        "mdbook": [".sidebar-scrollbox", "#sidebar"],
        "starlight": ["[data-has-sidebar]"],
        "mintlify": ['[class*="mintlify"]'],
    }
    for fw_name, selectors in _detect_map.items():
        for sel in selectors:
            try:
                if soup.select_one(sel):
                    return fw_name
            except Exception:
                pass
    # Check meta generator tags
    gen_tag = soup.select_one('meta[name="generator"]')
    if gen_tag:
        gen_content = (gen_tag.get("content") or "").lower()
        for fw in ["sphinx", "mkdocs", "hugo", "docusaurus", "vuepress", "vitepress", "nextra", "honkit", "mdbook", "antora", "starlight", "astro", "mintlify"]:
            if fw in gen_content:
                return fw
    return None


def _find_main_container(soup: BeautifulSoup) -> Tag | None:
    """Find the main content container using semantic HTML and heuristics.

    For documentation sites, uses framework-specific selectors for precise extraction
    and removes framework-specific boilerplate (sidebar, nav, footer).
    """
    # First: detect doc framework and use framework-specific extraction
    fw = _detect_doc_framework(soup)
    if fw and fw in DOC_FRAMEWORK_EXTRACTION:
        content_selectors, boilerplate_selectors = DOC_FRAMEWORK_EXTRACTION[fw]

        # Remove framework-specific boilerplate first
        for sel in boilerplate_selectors:
            for el in soup.select(sel):
                el.decompose()

        # Then find the content container
        for sel in content_selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                logger.debug(f"Doc framework '{fw}' content found via '{sel}'")
                return el

    # Standard semantic selectors
    for selector in [
        "main",
        "article",
        "[role='main']",
        "#content",
        "#main-content",
        ".main-content",
    ]:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 200:
            return el

    return None


def _smart_body_extract(soup: BeautifulSoup) -> Tag | None:
    """
    Extract body content aggressively stripping chrome (header, footer, aside).
    If we got here, there's no <main> or <article>, so be more aggressive.
    """
    body = soup.find("body")
    if not body:
        return None

    # Always remove top-level header — it's site chrome, not content
    for el in body.find_all("header", recursive=False):
        el.decompose()

    # Always remove top-level footer — site links, legal, etc.
    for el in body.find_all("footer", recursive=False):
        el.decompose()

    # Remove asides that are small (sidebars, ad blocks)
    for el in body.find_all("aside", recursive=False):
        if len(el.get_text(strip=True)) < 500:
            el.decompose()

    return body


def apply_tag_filters(
    html: str,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> str:
    """Apply include/exclude tag filters to HTML content."""
    soup = BeautifulSoup(html, "lxml")

    if exclude_tags:
        for selector in exclude_tags:
            for el in soup.select(selector):
                el.decompose()

    if include_tags:
        included_parts = []
        for selector in include_tags:
            for el in soup.select(selector):
                included_parts.append(str(el))
        if included_parts:
            return "\n".join(included_parts)

    return str(soup)


def _postprocess_markdown(markdown: str) -> str:
    """Post-processing pipeline — minimal cleaning to preserve maximum data.

    Code blocks (``` fenced) are protected from whitespace collapsing so that
    indentation, ASCII art, and tabular data inside <pre> sections are preserved.
    """
    # Split into code-block and non-code-block segments
    parts = re.split(r"(```[^\n]*\n.*?```)", markdown, flags=re.DOTALL)
    cleaned = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside a code fence — keep verbatim
            cleaned.append(part)
        else:
            # Outside code — apply cleaning
            part = re.sub(r"\n{3,}", "\n\n", part)
            part = re.sub(r"[ \t]+\n", "\n", part)
            part = re.sub(r"([^\n]) {3,}", r"\1 ", part)
            cleaned.append(part)
    markdown = "".join(cleaned)

    # Deduplicate repeated content (carousel slides, repeated sections)
    markdown = _deduplicate_content(markdown)

    # Remove only truly empty headings (no content at all)
    markdown = re.sub(r"^#{1,6}\s*$", "", markdown, flags=re.MULTILINE)

    # Final collapse of excessive newlines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


_CONVERTER = WebHarvestConverter(
    heading_style="ATX",
    bullets="-",
    newline_style="backslash",
    strip=["script", "style"],
)


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to clean GitHub Flavored Markdown.
    Tries Go sidecar first for speed, falls back to Python markdownify.
    """
    result = _convert_via_sidecar(html)
    if result is not None:
        return _postprocess_markdown(result)
    markdown = _CONVERTER.convert(html)
    return _postprocess_markdown(markdown)


def html_to_markdown_from_tag(tag: Tag | BeautifulSoup) -> str:
    """
    Fast path: convert a pre-parsed BS4 tag to markdown without re-parsing HTML.
    Saves ~50-100ms by skipping BeautifulSoup(html) inside markdownify.
    """
    markdown = _CONVERTER.convert_soup(tag)
    return _postprocess_markdown(markdown)


def _resolve_relative_urls(soup: BeautifulSoup, base_url: str) -> None:
    """Resolve all relative href/src attributes to absolute URLs in-place."""
    if not base_url:
        return
    for tag in soup.find_all(href=True):
        href = tag["href"].strip()
        if href and not href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            tag["href"] = urljoin(base_url, href)
    for tag in soup.find_all(src=True):
        src = tag["src"].strip()
        if src and not src.startswith(("data:", "javascript:")):
            tag["src"] = urljoin(base_url, src)


def _clean_soup_light(html: str, base_url: str = "") -> BeautifulSoup:
    """Smart content cleaning inspired by Crawl4AI's filtering pipeline.

    Applies multiple filtering passes:
    1. Strip non-renderable tags (scripts, styles, SVG, etc.)
    2. Remove invisible/hidden elements
    3. Remove hard junk (cookie banners, modals, ads, chat widgets)
    4. Per-block word-count filtering — remove trivial blocks (<10 words)
       unless they contain images, code, headings, or tables
    5. External image filtering — strip images hosted on other domains
    6. Social media link stripping — remove links to social platforms
    """
    soup = BeautifulSoup(html, "lxml")

    # Only remove tags that can NEVER produce meaningful markdown.
    # "noscript" kept — contains fallback image URLs for lazy-loaded content.
    LIGHT_JUNK_TAGS = {
        "script", "style", "svg", "path", "meta", "link",
        "canvas", "object", "embed", "source", "track", "template",
        "datalist", "iframe", "dialog", "select", "option",
    }
    for tag in soup.find_all(list(LIGHT_JUNK_TAGS)):
        tag.decompose()

    # Remove only truly invisible elements (display:none, hidden attribute)
    _remove_hidden_elements(soup)

    # Remove only hard junk that is never content (cookie banners, modals, chat widgets, ads)
    for selector in HARD_JUNK_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            pass

    # ── Crawl4AI-style per-block word-count filtering ──
    # Remove leaf-level blocks with fewer than BLOCK_WORD_THRESHOLD words,
    # unless the block contains valuable non-text content.
    _filter_thin_blocks(soup)

    # ── External image filtering ──
    # Remove <img> tags hosted on domains different from the page
    if base_url:
        _filter_external_images(soup, base_url)

    # ── Social media link stripping ──
    # Replace <a> tags pointing to social platforms with their plain text
    _strip_social_media_links(soup)

    return soup


# Minimum words for a block to be kept (lowered from 10 to preserve
# captions, bylines, short metadata, and CTAs)
BLOCK_WORD_THRESHOLD = 4

# Tags that contain valuable non-text content — never filtered by word count
_VALUABLE_CHILDREN = {"img", "pre", "code", "table", "video", "audio", "picture"}

# Tags that are block-level *wrappers* eligible for word-count filtering.
# Excludes content-bearing tags like <p>, <li>, <blockquote> which may
# legitimately be short (e.g. single-sentence paragraphs, list items).
_BLOCK_TAGS = {
    "div", "section", "aside", "figure", "figcaption",
    "details", "summary",
}

# Known social media domains (matches Crawl4AI defaults + extras)
_SOCIAL_MEDIA_DOMAINS = {
    "facebook.com", "www.facebook.com",
    "twitter.com", "www.twitter.com",
    "x.com", "www.x.com",
    "linkedin.com", "www.linkedin.com",
    "instagram.com", "www.instagram.com",
    "pinterest.com", "www.pinterest.com",
    "tiktok.com", "www.tiktok.com",
    "snapchat.com", "www.snapchat.com",
    "reddit.com", "www.reddit.com",
    "youtube.com", "www.youtube.com",
    "whatsapp.com", "www.whatsapp.com",
    "t.me",
    "discord.gg", "discord.com",
}


def _filter_thin_blocks(soup: BeautifulSoup) -> None:
    """Remove leaf-level blocks with fewer than BLOCK_WORD_THRESHOLD words.

    A 'leaf-level block' is a block-level element that doesn't contain other
    block-level children. This avoids accidentally removing a parent <div>
    that wraps multiple content paragraphs.

    Blocks containing images, code, tables, or headings are always kept
    regardless of word count — they carry non-textual value.
    """
    for el in list(soup.find_all(list(_BLOCK_TAGS))):
        # Skip if already decomposed
        if el.parent is None:
            continue

        # Skip if this block contains nested block children (it's a wrapper)
        if el.find(list(_BLOCK_TAGS)):
            continue

        # Skip if it contains valuable non-text content
        if el.find(list(_VALUABLE_CHILDREN)):
            continue

        # Skip if it contains any heading
        if el.find(re.compile(r"^h[1-6]$")):
            continue

        # Check word count
        text = el.get_text(strip=True)
        if len(text.split()) < BLOCK_WORD_THRESHOLD:
            el.decompose()


# Well-known CDN domains that host legitimate content images
_CDN_DOMAINS = {
    "cloudfront.net", "amazonaws.com", "akamaihd.net", "akamaized.net",
    "fastly.net", "cloudinary.com", "imgix.net", "shopify.com",
    "squarespace-cdn.com", "wp.com", "githubusercontent.com",
    "googleusercontent.com", "ggpht.com", "twimg.com", "fbcdn.net",
    "pinimg.com", "media-amazon.com", "ssl-images-amazon.com",
    "scene7.com", "unsplash.com", "pexels.com",
}


def _filter_external_images(soup: BeautifulSoup, base_url: str) -> None:
    """Remove tracking-pixel <img> tags while keeping CDN-hosted content images.

    Keeps images from the same domain, subdomains, and well-known CDN
    domains. Only removes tiny tracking pixels (1x1) from unknown domains.
    Preserves alt text as plain text when an external image is removed.
    """
    base_domain = urlparse(base_url).netloc
    base_parts = base_domain.split(".")
    root_domain = ".".join(base_parts[-2:]) if len(base_parts) >= 2 else base_domain

    for img in list(soup.find_all("img")):
        src = img.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(base_url, src)
        img_domain = urlparse(absolute).netloc
        # Keep same-domain images
        if not img_domain or img_domain.endswith(root_domain):
            continue
        # Keep images from well-known CDN domains
        if any(img_domain.endswith(cdn) for cdn in _CDN_DOMAINS):
            continue
        # For unknown external images, only remove if it looks like a tracking pixel
        width = img.get("width", "")
        height = img.get("height", "")
        if width in ("1", "0") and height in ("1", "0"):
            alt = img.get("alt", "").strip()
            if alt:
                img.replace_with(alt)
            else:
                img.decompose()


def _strip_social_media_links(soup: BeautifulSoup) -> None:
    """Replace social media <a> tags with their plain text.

    Doesn't remove the text content, just strips the link — so
    'Follow us on Twitter' keeps the text but loses the <a> wrapper.
    """
    for a_tag in list(soup.find_all("a", href=True)):
        href = a_tag["href"].strip()
        if not href:
            continue
        try:
            link_domain = urlparse(href).netloc.lower()
        except Exception:
            continue
        if link_domain in _SOCIAL_MEDIA_DOMAINS:
            # Replace <a> with its text content
            a_tag.replace_with(a_tag.get_text())


def extract_and_convert(
    raw_html: str,
    url: str,
    only_main_content: bool = False,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> tuple[str, str]:
    """
    Combined extraction + markdown conversion in minimal parses.

    Returns (clean_html_string, markdown_string).

    Performance: 1 BS4 parse for common case (vs 3 before).
    - Skips trafilatura when BS4 finds >500 chars (saves 150-250ms)
    - Passes soup tag directly to markdownify (saves 50-100ms re-parse)
    """
    if only_main_content:
        tag = _extract_main_tag(raw_html, url)
    else:
        # Crawl4AI-style: smart filtering (junk removal, per-block word threshold,
        # external image filtering, social media link stripping)
        tag = _clean_soup_light(raw_html, base_url=url)

    # Resolve relative URLs to absolute before markdown conversion
    _resolve_relative_urls(tag, url)

    if include_tags or exclude_tags:
        # Tag filters need to work on the soup — apply in-place
        if exclude_tags:
            for selector in exclude_tags:
                for el in tag.select(selector):
                    el.decompose()
        if include_tags:
            parts = []
            for selector in include_tags:
                for el in tag.select(selector):
                    parts.append(el)
            if parts:
                # Build a new soup from matched elements
                new_soup = BeautifulSoup("", "lxml")
                body = new_soup.new_tag("body")
                new_soup.append(body)
                for part in parts:
                    body.append(part)
                tag = new_soup

    clean_html = str(tag) if tag else ""

    # Try Go sidecar first (6-40x faster), fallback to Python markdownify
    markdown = None
    if clean_html:
        markdown = _convert_via_sidecar(clean_html)
        if markdown is not None:
            markdown = _postprocess_markdown(markdown)
    if markdown is None:
        markdown = html_to_markdown_from_tag(tag) if tag else ""

    return clean_html, markdown


def _remove_link_clusters(markdown: str) -> str:
    """Remove clusters of 5+ consecutive lines that are just short links (nav menus)."""
    lines = markdown.split("\n")
    result = []
    link_cluster = []

    # Pattern: line that is primarily a markdown link with short text
    link_line_re = re.compile(r"^\s*[-*]?\s*\[.{1,60}\]\(.*\)\s*$")

    for line in lines:
        if link_line_re.match(line):
            link_cluster.append(line)
        else:
            if len(link_cluster) >= 5:
                # This was a nav-like link cluster — drop it
                link_cluster = []
            else:
                # Short cluster — keep it (could be a legit list of links)
                result.extend(link_cluster)
                link_cluster = []
            result.append(line)

    # Handle trailing cluster
    if len(link_cluster) < 5:
        result.extend(link_cluster)

    return "\n".join(result)


def _deduplicate_content(markdown: str) -> str:
    """Remove duplicate paragraphs/sections (e.g., repeated carousel slides)."""
    blocks = re.split(r"\n{2,}", markdown)
    seen = set()
    unique_blocks = []

    for block in blocks:
        # Normalize for comparison: lowercase, collapse whitespace
        normalized = re.sub(r"\s+", " ", block.strip().lower())
        # Skip short blocks — only dedup substantial repeated paragraphs
        if len(normalized) < 80:
            unique_blocks.append(block)
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique_blocks.append(block)

    return "\n\n".join(unique_blocks)


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract all navigable links from HTML, resolved to absolute URLs.

    Covers <a href>, <link rel=next/prev/canonical>, <form action>,
    and data-href attributes used by SPAs.
    """
    soup = BeautifulSoup(html, "lxml")
    links = set()

    def _add(url: str) -> None:
        url = url.strip()
        if not url or url.startswith(("mailto:", "tel:", "javascript:", "data:")):
            return
        absolute = urljoin(base_url, url)
        parsed = urlparse(absolute)
        frag = parsed.fragment
        if frag and (frag.startswith("/") or frag.startswith("!/")):
            links.add(absolute)  # SPA route fragment — keep
        else:
            links.add(parsed._replace(fragment="").geturl())

    # Standard <a href>
    for a_tag in soup.find_all("a", href=True):
        _add(a_tag["href"])

    # <link rel="next|prev|canonical"> — pagination and canonical hints
    for link_tag in soup.find_all("link", href=True):
        rel = " ".join(link_tag.get("rel", []))
        if any(r in rel for r in ("next", "prev", "canonical")):
            _add(link_tag["href"])

    # <form action> — search and filter endpoints
    for form in soup.find_all("form", action=True):
        action = form["action"].strip()
        if action and not action.startswith("javascript:"):
            _add(action)

    # data-href / data-url — SPA navigation attributes
    for el in soup.find_all(attrs={"data-href": True}):
        _add(el["data-href"])
    for el in soup.find_all(attrs={"data-url": True}):
        _add(el["data-url"])

    return sorted(links)


def extract_links_detailed(html: str, base_url: str) -> dict:
    """
    Extract detailed link analysis - internal vs external, with anchor text.
    Rich link analysis with internal/external classification and anchor text.
    """
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc

    internal = []
    external = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        clean_url = parsed._replace(fragment="").geturl()
        text = a_tag.get_text(strip=True)
        title = a_tag.get("title", "")
        rel = a_tag.get("rel", [])
        target = a_tag.get("target", "")

        link_data = {
            "url": clean_url,
            "text": text or None,
        }
        if title:
            link_data["title"] = title
        if "nofollow" in rel:
            link_data["nofollow"] = True
        if target == "_blank":
            link_data["new_tab"] = True

        if parsed.netloc == base_domain:
            internal.append(link_data)
        else:
            external.append(link_data)

    return {
        "total": len(internal) + len(external),
        "internal": {"count": len(internal), "links": internal},
        "external": {"count": len(external), "links": external},
    }


def extract_structured_data(html: str) -> dict:
    """
    Extract all structured/semantic data embedded in the HTML.

    Extracts:
    - JSON-LD (Schema.org structured data)
    - OpenGraph meta tags (social sharing)
    - Twitter Card meta tags
    - All meta tags
    - Microdata attributes

    Comprehensive structured data extraction from multiple sources.
    """
    # Parse the ORIGINAL html (before junk removal) to get script tags
    soup = BeautifulSoup(html, "lxml")
    result = {}

    # 1. JSON-LD - the most valuable structured data
    json_ld = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            text = script.string or script.get_text()
            if text:
                data = json.loads(text)
                json_ld.append(data)
        except (json.JSONDecodeError, TypeError):
            pass
    if json_ld:
        result["json_ld"] = json_ld

    # 2. OpenGraph tags (accumulate lists for keys that can repeat, e.g. og:image)
    _OG_MULTI_KEYS = {"image", "image:url", "image:width", "image:height",
                       "image:type", "image:alt", "video", "video:url",
                       "video:type", "video:width", "video:height", "audio"}
    og: dict = {}
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        if prop.startswith("og:"):
            key = prop[3:]
            content = meta.get("content", "")
            if key in _OG_MULTI_KEYS:
                og.setdefault(key, [])
                og[key].append(content)
            else:
                og[key] = content
    if og:
        result["open_graph"] = og

    # 3. Twitter Card tags
    twitter = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name", "")
        if name.startswith("twitter:"):
            key = name[8:]
            twitter[key] = meta.get("content", "")
    if twitter:
        result["twitter_card"] = twitter

    # 4. All meta tags (useful catch-all)
    meta_tags = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property") or meta.get("http-equiv")
        content = meta.get("content", "")
        if name and content:
            meta_tags[name] = content
    if meta_tags:
        result["meta_tags"] = meta_tags

    return result


# ---------------------------------------------------------------------------
# Product data extraction (no LLM — schema.org + microdata + OG)
# ---------------------------------------------------------------------------

_PRODUCT_TYPES = {
    "product", "product/group", "og:product", "og:product.item",
    "indivio:product",
}

_SCHEMA_PRODUCT_TYPES = {
    "Product", "https://schema.org/Product", "http://schema.org/Product",
    "IndividualProduct", "ProductModel", "ProductGroup",
}


def _has_product_signals(structured_data: dict | None, html: str) -> bool:
    """Quick bail — check if the page has any product indicators at all.

    Avoids full parsing cost on blog posts, about pages, etc.
    """
    if structured_data:
        # Check JSON-LD
        for item in structured_data.get("json_ld", []):
            items = item if isinstance(item, list) else [item]
            for obj in items:
                if isinstance(obj, dict):
                    t = obj.get("@type", "")
                    types = t if isinstance(t, list) else [t]
                    if any(tp in _SCHEMA_PRODUCT_TYPES for tp in types):
                        return True
                    # Check @graph array
                    for graph_item in obj.get("@graph", []):
                        if isinstance(graph_item, dict):
                            gt = graph_item.get("@type", "")
                            gtypes = gt if isinstance(gt, list) else [gt]
                            if any(gtp in _SCHEMA_PRODUCT_TYPES for gtp in gtypes):
                                return True
        # Check OG type
        og = structured_data.get("open_graph", {})
        if og.get("type", "").lower() in _PRODUCT_TYPES:
            return True
        # Check meta tags for og:type product
        meta = structured_data.get("meta_tags", {})
        if meta.get("og:type", "").lower() in _PRODUCT_TYPES:
            return True

    # Check for microdata itemtype containing Product (fast substring check)
    if 'itemtype' in html and 'roduct' in html:
        return True

    # Check for product OG meta tags in raw HTML
    if 'product:price:amount' in html:
        return True

    return False


def _parse_microdata_item(el: Tag) -> dict:
    """Recursively parse a single microdata itemscope element into a dict."""
    result = {}
    item_type = el.get("itemtype", "")
    if item_type:
        result["@type"] = item_type

    for child in el.find_all(True, recursive=True):
        prop = child.get("itemprop")
        if not prop:
            continue
        # Skip properties that belong to a nested itemscope (not ours).
        # Walk up from child to el; if we hit another itemscope first, skip.
        owner = child.parent
        belongs_to_nested = False
        while owner is not None and owner is not el:
            if isinstance(owner, Tag) and owner.get("itemscope") is not None:
                belongs_to_nested = True
                break
            owner = owner.parent
        if belongs_to_nested:
            continue

        # If the child is itself an itemscope, recurse
        if child.get("itemscope") is not None:
            value = _parse_microdata_item(child)
        elif child.name == "meta":
            value = child.get("content", "")
        elif child.name == "link":
            value = child.get("href", "")
        elif child.name == "img":
            value = child.get("src", "")
        elif child.name == "time":
            value = child.get("datetime", child.get_text(strip=True))
        elif child.name == "data":
            value = child.get("value", child.get_text(strip=True))
        else:
            value = child.get("content", "") or child.get_text(strip=True)

        # Multiple values for the same property → list
        if prop in result:
            existing = result[prop]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[prop] = [existing, value]
        else:
            result[prop] = value

    return result


def _extract_microdata_items(soup: BeautifulSoup) -> list[dict]:
    """Extract all microdata items (both top-level and nested with itemprop).

    Nested itemscopes (e.g. Offer inside Product) are parsed recursively
    by _parse_microdata_item, but we also collect them at top level so
    product extraction can merge Offer data that lives in a nested scope.
    """
    items = []
    for el in soup.find_all(attrs={"itemscope": True}):
        items.append(_parse_microdata_item(el))
    return items


def _safe_str(val) -> str | None:
    """Coerce a value to string, returning None for empty/missing."""
    if val is None:
        return None
    if isinstance(val, dict):
        return None
    s = str(val).strip()
    return s if s else None


def _merge_jsonld_product(product: dict, jsonld: dict) -> None:
    """Merge a JSON-LD Product object into the unified product dict."""
    if not product.get("name"):
        product["name"] = _safe_str(jsonld.get("name"))
    if not product.get("description"):
        product["description"] = _safe_str(jsonld.get("description"))
    if not product.get("sku"):
        product["sku"] = _safe_str(jsonld.get("sku")) or _safe_str(jsonld.get("mpn")) or _safe_str(jsonld.get("gtin13"))

    # Brand
    if not product.get("brand"):
        brand = jsonld.get("brand")
        if isinstance(brand, dict):
            product["brand"] = _safe_str(brand.get("name"))
        elif isinstance(brand, str):
            product["brand"] = _safe_str(brand)

    # Images
    if not product.get("images"):
        img = jsonld.get("image")
        if isinstance(img, list):
            product["images"] = [str(i) for i in img if i]
        elif isinstance(img, str) and img:
            product["images"] = [img]
        elif isinstance(img, dict):
            url = img.get("url") or img.get("contentUrl")
            if url:
                product["images"] = [str(url)]

    # Offers / pricing
    offers = jsonld.get("offers")
    if offers and not product.get("price"):
        offer_list = offers if isinstance(offers, list) else [offers]
        for offer in offer_list:
            if not isinstance(offer, dict):
                continue
            # AggregateOffer
            if offer.get("@type") in ("AggregateOffer", "https://schema.org/AggregateOffer"):
                low = _safe_str(offer.get("lowPrice"))
                high = _safe_str(offer.get("highPrice"))
                if low and high and low != high:
                    product["price"] = f"{low}-{high}"
                elif low:
                    product["price"] = low
                product["currency"] = _safe_str(offer.get("priceCurrency")) or product.get("currency")
                avail = offer.get("availability", "")
                if avail:
                    product["availability"] = str(avail).rsplit("/", 1)[-1]
                break
            # Regular Offer
            price = _safe_str(offer.get("price"))
            if price:
                product["price"] = price
                product["currency"] = _safe_str(offer.get("priceCurrency")) or product.get("currency")
                avail = offer.get("availability", "")
                if avail:
                    product["availability"] = str(avail).rsplit("/", 1)[-1]
                break

    # Rating
    if not product.get("rating"):
        rating = jsonld.get("aggregateRating")
        if isinstance(rating, dict):
            r = {}
            val = rating.get("ratingValue")
            if val is not None:
                try:
                    r["value"] = float(val)
                except (ValueError, TypeError):
                    pass
            cnt = rating.get("ratingCount") or rating.get("reviewCount")
            if cnt is not None:
                try:
                    r["count"] = int(cnt)
                except (ValueError, TypeError):
                    pass
            if r:
                product["rating"] = r


def _merge_microdata_product(product: dict, item: dict) -> None:
    """Merge a microdata Product item into the unified product dict."""
    if not product.get("name"):
        product["name"] = _safe_str(item.get("name"))
    if not product.get("description"):
        product["description"] = _safe_str(item.get("description"))
    if not product.get("sku"):
        product["sku"] = _safe_str(item.get("sku")) or _safe_str(item.get("mpn"))

    if not product.get("brand"):
        brand = item.get("brand")
        if isinstance(brand, dict):
            product["brand"] = _safe_str(brand.get("name"))
        elif isinstance(brand, str):
            product["brand"] = _safe_str(brand)

    if not product.get("images"):
        img = item.get("image")
        if isinstance(img, list):
            product["images"] = [str(i) for i in img if i]
        elif isinstance(img, str) and img:
            product["images"] = [img]

    # Offers from microdata
    offers = item.get("offers")
    if offers and not product.get("price"):
        offer_list = offers if isinstance(offers, list) else [offers]
        for offer in offer_list:
            if not isinstance(offer, dict):
                continue
            price = _safe_str(offer.get("price"))
            if price:
                product["price"] = price
                product["currency"] = _safe_str(offer.get("priceCurrency")) or product.get("currency")
                avail = offer.get("availability", "")
                if avail:
                    product["availability"] = str(avail).rsplit("/", 1)[-1]
                break

    if not product.get("rating"):
        rating = item.get("aggregateRating")
        if isinstance(rating, dict):
            r = {}
            val = rating.get("ratingValue")
            if val is not None:
                try:
                    r["value"] = float(val)
                except (ValueError, TypeError):
                    pass
            cnt = rating.get("ratingCount") or rating.get("reviewCount")
            if cnt is not None:
                try:
                    r["count"] = int(cnt)
                except (ValueError, TypeError):
                    pass
            if r:
                product["rating"] = r


def _merge_og_product(product: dict, og: dict, meta: dict) -> None:
    """Merge OpenGraph product tags into the unified product dict."""
    if not product.get("name"):
        product["name"] = _safe_str(og.get("title"))
    if not product.get("description"):
        product["description"] = _safe_str(og.get("description"))
    if not product.get("images"):
        img = og.get("image")
        if img:
            product["images"] = [img] if isinstance(img, str) else [str(img)]

    # OG product-specific tags (product:price:amount, product:price:currency)
    if not product.get("price"):
        price = meta.get("product:price:amount")
        if price:
            product["price"] = _safe_str(price)
    if not product.get("currency"):
        currency = meta.get("product:price:currency")
        if currency:
            product["currency"] = _safe_str(currency)

    if not product.get("brand"):
        brand = meta.get("product:brand")
        if brand:
            product["brand"] = _safe_str(brand)

    if not product.get("availability"):
        avail = meta.get("product:availability")
        if avail:
            product["availability"] = _safe_str(avail)


def extract_product_data(html: str, structured_data: dict | None = None) -> dict | None:
    """Extract unified product data from multiple sources (no LLM).

    Priority: JSON-LD > microdata > OpenGraph.
    Returns None for non-product pages (fast bail via signal check).
    """
    if not _has_product_signals(structured_data, html):
        return None

    product: dict = {}

    # 1. JSON-LD Product (highest priority) — merge ALL matching objects
    if structured_data:
        for item in structured_data.get("json_ld", []):
            items = item if isinstance(item, list) else [item]
            for obj in items:
                if not isinstance(obj, dict):
                    continue
                t = obj.get("@type", "")
                types = t if isinstance(t, list) else [t]
                if any(tp in _SCHEMA_PRODUCT_TYPES for tp in types):
                    _merge_jsonld_product(product, obj)
                # Check @graph
                for graph_item in obj.get("@graph", []):
                    if isinstance(graph_item, dict):
                        gt = graph_item.get("@type", "")
                        gtypes = gt if isinstance(gt, list) else [gt]
                        if any(gtp in _SCHEMA_PRODUCT_TYPES for gtp in gtypes):
                            _merge_jsonld_product(product, graph_item)

    # 2. Microdata (fills gaps) — merge ALL matching items
    soup = BeautifulSoup(html, "lxml")
    microdata_items = _extract_microdata_items(soup)
    for item in microdata_items:
        item_type = item.get("@type", "")
        if "Product" in item_type or "product" in item_type.lower():
            _merge_microdata_product(product, item)

    # 3. OpenGraph (fills remaining gaps)
    if structured_data:
        og = structured_data.get("open_graph", {})
        meta = structured_data.get("meta_tags", {})
        _merge_og_product(product, og, meta)

    # Only return if we found at least a name or price
    if product.get("name") or product.get("price"):
        # Clean up None values
        return {k: v for k, v in product.items() if v is not None}

    return None


def extract_headings(html: str) -> list[dict]:
    """
    Extract heading hierarchy from HTML.
    Returns structured heading tree useful for understanding page structure.
    """
    soup = BeautifulSoup(html, "lxml")
    headings = []

    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        level = int(tag.name[1])
        text = tag.get_text(strip=True)
        if text:
            heading_data = {"level": level, "text": text}
            # Include id for anchor linking
            tag_id = tag.get("id")
            if tag_id:
                heading_data["id"] = tag_id
            headings.append(heading_data)

    return headings


def _parse_srcset(srcset: str, base_url: str) -> list[dict]:
    """Parse srcset attribute into list of {url, descriptor} dicts."""
    entries = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if tokens:
            url = urljoin(base_url, tokens[0])
            desc = tokens[1] if len(tokens) > 1 else ""
            entries.append({"url": url, "descriptor": desc})
    return entries


def extract_images(html: str, base_url: str) -> list[dict]:
    """Extract all images with their metadata, including srcset and picture sources."""
    soup = BeautifulSoup(html, "lxml")
    images = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        absolute_src = urljoin(base_url, src)
        image_data: dict = {
            "src": absolute_src,
            "alt": img.get("alt", ""),
        }
        width = img.get("width")
        height = img.get("height")
        if width:
            image_data["width"] = width
        if height:
            image_data["height"] = height
        loading = img.get("loading")
        if loading:
            image_data["loading"] = loading
        # Responsive image sources
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        if srcset:
            image_data["srcset"] = _parse_srcset(srcset, base_url)
        images.append(image_data)

    # <picture><source> elements
    for picture in soup.find_all("picture"):
        for source in picture.find_all("source"):
            srcset = source.get("srcset") or ""
            if srcset:
                media = source.get("media", "")
                img_type = source.get("type", "")
                for entry in _parse_srcset(srcset, base_url):
                    images.append({
                        "src": entry["url"],
                        "alt": "",
                        "media": media,
                        "type": img_type,
                    })

    return images


def extract_metadata(
    html: str, url: str, status_code: int = 200, response_headers: dict | None = None
) -> dict:
    """
    Extract comprehensive page metadata from HTML.
    Much richer than basic title/description - includes SEO signals,
    performance hints, and content analysis.
    """
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        description = meta_desc.get("content", "")

    # Also try og:description
    if not description:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc:
            description = og_desc.get("content", "")

    language = ""
    html_tag = soup.find("html")
    if html_tag:
        language = html_tag.get("lang", "")

    # Open Graph image
    og_image = ""
    og_img_tag = soup.find("meta", attrs={"property": "og:image"})
    if og_img_tag:
        og_image = og_img_tag.get("content", "")

    # Canonical URL
    canonical = ""
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag:
        canonical = canonical_tag.get("href", "")

    # Favicon
    favicon = ""
    for rel_type in [["icon"], ["shortcut", "icon"], ["apple-touch-icon"]]:
        fav_tag = soup.find("link", attrs={"rel": rel_type})
        if fav_tag:
            favicon = urljoin(url, fav_tag.get("href", ""))
            break

    # Robots meta
    robots = ""
    robots_meta = soup.find("meta", attrs={"name": "robots"})
    if robots_meta:
        robots = robots_meta.get("content", "")

    # Count words in body text
    body = soup.find("body")
    word_count = 0
    body_text = ""
    if body:
        body_text = body.get_text(separator=" ", strip=True)
        word_count = len(body_text.split())

    # Reading time estimate (average 200 words per minute)
    reading_time_seconds = math.ceil(word_count / 200) * 60 if word_count > 0 else 0

    # Content size
    content_length = len(html)

    result = {
        "title": title,
        "description": description,
        "language": language,
        "source_url": url,
        "status_code": status_code,
        "word_count": word_count,
        "reading_time_seconds": reading_time_seconds,
        "content_length": content_length,
    }

    if og_image:
        result["og_image"] = og_image
    if canonical:
        result["canonical_url"] = canonical
    if favicon:
        result["favicon"] = favicon
    if robots:
        result["robots"] = robots

    # Response headers (if provided)
    if response_headers:
        # Pick the most useful headers
        useful_headers = {}
        for key in [
            "content-type",
            "content-length",
            "content-encoding",
            "transfer-encoding",
            "link",
            "server",
            "x-powered-by",
            "cache-control",
            "x-frame-options",
            "content-security-policy",
            "x-robots-tag",
            "last-modified",
            "etag",
        ]:
            val = response_headers.get(key)
            if val:
                useful_headers[key] = val
        if useful_headers:
            result["response_headers"] = useful_headers

    return result
