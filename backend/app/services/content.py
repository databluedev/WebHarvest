import json
import logging
import math
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

logger = logging.getLogger(__name__)

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


def extract_main_content(html: str, url: str = "") -> str:
    """
    Multi-pass content extraction that produces clean, high-quality output.

    Strategy:
    1. Clean junk tags (script, style, video, audio, etc.)
    2. Aggressively remove ALL boilerplate (nav, modals, cookie banners, etc.)
    3. Remove hidden/invisible elements
    4. Try to find explicit main content container
    5. If no container found, use aggressive body extraction
    6. Compare trafilatura result - use whichever is more complete
    """
    soup = BeautifulSoup(html, "lxml")

    # Step 1: Remove definite junk tags
    for tag in soup.find_all(list(JUNK_TAGS)):
        tag.decompose()

    # Step 2: Remove ALL boilerplate — no text-length mercy
    for selector in BOILERPLATE_SELECTORS:
        try:
            for el in soup.select(selector):
                # Protect elements inside main/article content containers
                if _is_inside_main_content(el):
                    continue
                el.decompose()
        except Exception:
            pass

    # Step 3: Remove hidden/invisible elements
    _remove_hidden_elements(soup)

    # Step 4: Remove form elements (search bars, dropdowns, inputs)
    for form in soup.find_all("form"):
        # Keep forms that contain substantial text (contact forms, etc.)
        form_text = form.get_text(strip=True)
        if len(form_text) < 300:
            form.decompose()

    # Step 5: Try to find main content container
    main_content = _find_main_container(soup)

    # Step 6: Aggressive body extraction as fallback
    if not main_content:
        main_content = _smart_body_extract(soup)

    # Step 7: Compare with trafilatura and pick the more complete result
    bs4_html = str(main_content) if main_content else ""
    bs4_text_len = (
        len(BeautifulSoup(bs4_html, "lxml").get_text(strip=True)) if bs4_html else 0
    )

    traf_html = ""
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
            traf_html = traf_result
    except Exception as e:
        logger.debug(f"Trafilatura extraction failed: {e}")

    traf_text_len = (
        len(BeautifulSoup(traf_html, "lxml").get_text(strip=True)) if traf_html else 0
    )

    # Pick whichever captured MORE content
    if bs4_text_len > traf_text_len * 1.2:
        logger.debug(
            f"Using BS4 extraction ({bs4_text_len} chars > trafilatura {traf_text_len} chars)"
        )
        return bs4_html
    elif traf_text_len > 100:
        logger.debug(f"Using trafilatura extraction ({traf_text_len} chars)")
        return traf_html
    else:
        return bs4_html or str(soup.body) if soup.body else str(soup)


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


def _find_main_container(soup: BeautifulSoup) -> Tag | None:
    """Find the main content container using semantic HTML and heuristics."""
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


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to clean GitHub Flavored Markdown.
    Uses custom converter that preserves links, images, code blocks, and structure.
    Includes aggressive post-processing for clean, production-quality output.
    """
    converter = WebHarvestConverter(
        heading_style="ATX",
        bullets="-",
        newline_style="backslash",
        strip=["script", "style", "noscript"],
    )
    markdown = converter.convert(html)

    # === Post-processing pipeline for clean output ===

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
    markdown = markdown.strip()

    return markdown


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
