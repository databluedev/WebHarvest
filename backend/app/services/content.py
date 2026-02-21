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
            timeout=10.0,
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

# Tags that are always junk — can't be rendered as meaningful markdown
JUNK_TAGS = {
    "script",
    "style",
    "noscript",
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

# Selectors ALWAYS removed — these are never useful page content
BOILERPLATE_SELECTORS = [
    # Navigation — always boilerplate (mega-menus, site nav, etc.)
    "nav",
    "[role='navigation']",
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
    "[class*='video-player']",
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
    # Sidebar elements that are typically ads/promos
    ".sidebar-ad",
    "[class*='ad-slot']",
    "[class*='advertisement']",
    # Chat widgets
    "[class*='chat-widget']",
    "[class*='live-chat']",
    "#hubspot-messages-iframe-container",
]

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

    # Remove form elements (search bars, dropdowns, inputs)
    for form in soup.find_all("form"):
        form_text = form.get_text(strip=True)
        if len(form_text) < 300:
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

    # aria-hidden elements (usually decorative)
    aria_hidden = list(soup.find_all(attrs={"aria-hidden": "true"}))
    for el in aria_hidden:
        try:
            if len(el.get_text(strip=True)) < 100:
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
    """Post-processing pipeline for clean markdown output."""
    # 1. Collapse 3+ newlines into 2
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    # 2. Remove trailing whitespace on lines
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    # 3. Remove excessive spaces (but preserve indentation)
    markdown = re.sub(r"([^\n]) {3,}", r"\1 ", markdown)

    # 4. Remove navigation-like link clusters (5+ consecutive short link-only lines)
    markdown = _remove_link_clusters(markdown)

    # 5. Deduplicate repeated content (carousel slides, repeated sections)
    markdown = _deduplicate_content(markdown)

    # 6. Remove empty headings and orphaned markers
    markdown = re.sub(r"^#{1,6}\s*$", "", markdown, flags=re.MULTILINE)
    # Remove lines that are just dashes, pipes, or bullets with no content
    markdown = re.sub(r"^[\s\-\|*>]+$", "", markdown, flags=re.MULTILINE)

    # 7. Final collapse of excessive newlines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


_CONVERTER = WebHarvestConverter(
    heading_style="ATX",
    bullets="-",
    newline_style="backslash",
    strip=["script", "style", "noscript"],
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


def extract_and_convert(
    raw_html: str,
    url: str,
    only_main_content: bool = True,
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
        tag = BeautifulSoup(raw_html, "lxml")

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
        # Skip very short blocks (empty lines, single words)
        if len(normalized) < 20:
            unique_blocks.append(block)
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique_blocks.append(block)

    return "\n\n".join(unique_blocks)


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract all links from HTML, resolved to absolute URLs."""
    soup = BeautifulSoup(html, "lxml")
    links = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        # Remove fragments
        parsed = urlparse(absolute)
        clean_url = parsed._replace(fragment="").geturl()
        links.add(clean_url)

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

    # 2. OpenGraph tags
    og = {}
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        if prop.startswith("og:"):
            key = prop[3:]
            og[key] = meta.get("content", "")
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


def extract_images(html: str, base_url: str) -> list[dict]:
    """Extract all images with their metadata."""
    soup = BeautifulSoup(html, "lxml")
    images = []

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        absolute_src = urljoin(base_url, src)
        image_data = {
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
        images.append(image_data)

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
