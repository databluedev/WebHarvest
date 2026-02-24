"""Google Maps scraper — fetches and parses Google Maps place data.

Strategy: nodriver (undetected Chrome + Xvfb) — Google Maps requires full
JavaScript rendering, no HTTP-only fallback is possible.

Supports:
  - Search mode: find places matching a query + optional coordinates/filters
  - Place details mode: detailed info for a single place (by place_id, cid, or query)

Results are cached in Redis for 5 minutes.
"""

import asyncio
import hashlib
import json
import logging
import math
import re
import time
from urllib.parse import quote_plus, unquote

from bs4 import BeautifulSoup

from app.config import settings
from app.schemas.data_google import (
    GoogleMapsPlace,
    GoogleMapsResponse,
    GoogleMapsReview,
    RelatedSearch,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_MAX_SCROLL_ROUNDS = 5  # Max scroll iterations for loading more results


# ═══════════════════════════════════════════════════════════════════
# Cache key
# ═══════════════════════════════════════════════════════════════════


def _cache_key(
    query: str | None,
    coordinates: str | None,
    place_id: str | None,
    cid: str | None,
    num: int,
    lang: str,
    type_filter: str | None,
) -> str:
    raw = (
        f"maps|{query or ''}|{coordinates or ''}|{place_id or ''}"
        f"|{cid or ''}|{num}|{lang}|{type_filter or ''}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:maps:{h}"


# ═══════════════════════════════════════════════════════════════════
# URL builder
# ═══════════════════════════════════════════════════════════════════


def _zoom_from_radius(radius: int) -> int:
    """Calculate Google Maps zoom level from search radius in meters."""
    if radius <= 0:
        return 14
    # Formula: zoom ≈ 14 - log2(radius / 1000)
    zoom = 14 - math.log2(max(radius, 100) / 1000)
    return max(1, min(21, round(zoom)))


def _build_search_url(
    query: str,
    coordinates: str | None = None,
    radius: int | None = None,
    zoom: int | None = None,
    lang: str = "en",
    type_filter: str | None = None,
) -> str:
    """Build a Google Maps search URL."""
    search_term = query
    if type_filter and type_filter.lower() not in query.lower():
        search_term = f"{type_filter} {query}"

    encoded = quote_plus(search_term)
    url = f"https://www.google.com/maps/search/{encoded}"

    if coordinates:
        z = zoom or _zoom_from_radius(radius or 5000)
        url += f"/@{coordinates},{z}z"

    url += f"?hl={lang}"
    return url


def _build_place_url(
    place_id: str | None = None,
    cid: str | None = None,
    data: str | None = None,
    query: str | None = None,
    lang: str = "en",
    coordinates: str | None = None,
) -> str:
    """Build a Google Maps place details URL.

    The /data=!4m2!3m1!1s{identifier} format is required to trigger the
    details side-panel. Without it, Google Maps shows only the map view
    and the DOM elements remain empty.

    If coordinates are provided, they're included in the URL so the page
    can resolve them — Google Maps doesn't expose coordinates for CID-only
    navigation otherwise.
    """
    at_coords = f"@{coordinates},17z" if coordinates else "@0,0,15z"

    if cid:
        return (
            f"https://www.google.com/maps/place/x/{at_coords}"
            f"/data=!4m2!3m1!1s{cid}?hl={lang}"
        )
    if place_id:
        return (
            f"https://www.google.com/maps/place/x/{at_coords}"
            f"/data=!4m2!3m1!1s{place_id}?hl={lang}"
        )
    if data:
        return (
            f"https://www.google.com/maps/place/x/{at_coords}"
            f"/data={data}?hl={lang}"
        )
    if query:
        # For query-based lookups, use search URL instead (returns search results)
        return (
            f"https://www.google.com/maps/search/"
            f"{quote_plus(query)}?hl={lang}"
        )
    raise ValueError("One of place_id, cid, data, or query is required")


# ═══════════════════════════════════════════════════════════════════
# nodriver fetch (uses persistent browser pool)
# ═══════════════════════════════════════════════════════════════════


async def _fetch_maps_search(
    url: str, num_results: int = 20
) -> str | None:
    """Fetch Google Maps search results page using the persistent browser pool.

    Uses NoDriverPool to avoid the 5-10s browser startup cost on each call.
    Fast redirect detection: checks URL after 2s instead of waiting for
    selector timeouts (saves 10+ seconds on city-name searches).
    Scrolls the results feed to load more places if needed.
    """
    from app.services.nodriver_helper import NoDriverPool

    pool = NoDriverPool.get()
    tab = None
    try:
        tab = await pool.acquire_tab(url)
        if tab is None:
            logger.warning("Maps search: failed to acquire tab")
            return None

        # Brief initial wait for navigation
        await tab.sleep(1)

        # Fast redirect detection: check URL immediately
        current_url = str(await tab.evaluate("window.location.href") or "")
        if "/maps/place/" in current_url:
            # Google redirected to a place page (e.g. city name search).
            # Return HTML immediately for fallback parsing as place_details.
            logger.info("Maps redirect to place detected, returning for fallback")
            html = await tab.get_content()
            return html

        # Poll for search cards — check every 0.5s, max 3.5s
        cards_found = False
        for attempt in range(7):  # 7 × 0.5s = max 3.5s wait
            card_count = await tab.evaluate(
                "document.querySelectorAll('div.Nv2PK').length"
            )
            if card_count and int(card_count) > 0:
                cards_found = True
                logger.info(
                    "Maps search: %s cards at attempt %d", card_count, attempt
                )
                break
            await tab.sleep(0.5)

        if not cards_found:
            logger.info("Maps search: no cards after polling")

        # Scroll to load more results if needed
        scrolls_needed = min(
            _MAX_SCROLL_ROUNDS,
            max(0, (num_results - 20) // 20),
        )
        for i in range(scrolls_needed):
            await tab.evaluate(
                """
                const feed = document.querySelector("div[role='feed']");
                if (feed) feed.scrollTo(0, feed.scrollHeight);
                """
            )
            await tab.sleep(2)
            count = await tab.evaluate(
                "document.querySelectorAll('div[role=\"article\"]').length"
            )
            logger.info("Maps scroll %d: %s results loaded", i + 1, count)
            if count and int(count) >= num_results:
                break

        html = await tab.get_content()
        if not html:
            html = await tab.evaluate("document.documentElement.outerHTML")
        return html

    except Exception as e:
        logger.warning("Maps search fetch failed: %s", e)
        return None
    finally:
        if tab:
            await pool.release_tab(tab)


async def _fetch_maps_details(url: str) -> tuple[str | None, dict]:
    """Fetch Google Maps place details page using the persistent browser pool.

    Requires a URL with /data= parameter to trigger the details panel.
    Polls for actual text content before grabbing the HTML.

    Returns:
        (html, metadata) — metadata has coordinates extracted via JS.
    """
    from app.services.nodriver_helper import NoDriverPool

    pool = NoDriverPool.get()
    tab = None
    try:
        tab = await pool.acquire_tab(url)
        if tab is None:
            logger.warning("Maps details: failed to acquire tab")
            return None, {}

        # Wait for the page structure
        try:
            await tab.select("div[role='main']", timeout=8)
        except Exception:
            pass

        await tab.sleep(1)

        # Dismiss promo overlays if present
        await tab.evaluate("""
            (() => {
                const btn = document.querySelector(
                    'button[jsaction*="reveal.card.close"], '
                    + '[role="dialog"] button[aria-label="Close"]'
                );
                if (btn) btn.click();
            })()
        """)

        # Poll for actual content — the details panel loads asynchronously
        for attempt in range(10):
            has_content = await tab.evaluate("""
                (() => {
                    const h1 = document.querySelector('h1.DUwDvf, div[role="main"] h1');
                    const addr = document.querySelector('[data-item-id="address"]');
                    const title = h1 ? h1.innerText.trim() : '';
                    return title.length > 0 || addr !== null;
                })()
            """)
            if has_content:
                logger.info("Maps details content ready at attempt %d", attempt)
                break
            await tab.sleep(0.5)

        # Brief settle time for remaining sections (hours, reviews)
        await tab.sleep(1)

        # Extract coordinates via JS
        metadata: dict = {}
        try:
            coords_json = await tab.evaluate("""
                (() => {
                    const url = window.location.href;
                    const m = url.match(/@([\\.\\d-]+),([\\.\\d-]+)/);
                    if (m) {
                        const lat = parseFloat(m[1]);
                        const lng = parseFloat(m[2]);
                        if (Math.abs(lat) > 0.01 || Math.abs(lng) > 0.01) {
                            return JSON.stringify({lat, lng});
                        }
                    }
                    const og = document.querySelector('meta[property="og:image"]');
                    if (og) {
                        const c = og.content || '';
                        const m2 = c.match(/center=([\\d.-]+)%2C([\\d.-]+)/);
                        if (m2) {
                            const lat = parseFloat(m2[1]);
                            const lng = parseFloat(m2[2]);
                            if (Math.abs(lat) > 0.01 || Math.abs(lng) > 0.01) {
                                return JSON.stringify({lat, lng});
                            }
                        }
                    }
                    return null;
                })()
            """)
            if coords_json and coords_json != "null":
                import json as _json

                coords = _json.loads(coords_json)
                metadata["latitude"] = coords["lat"]
                metadata["longitude"] = coords["lng"]
        except Exception:
            pass

        html = await tab.get_content()
        if not html:
            html = await tab.evaluate("document.documentElement.outerHTML")
        return html, metadata

    except Exception as e:
        logger.warning("Maps details fetch failed: %s", e)
        return None, {}
    finally:
        if tab:
            await pool.release_tab(tab)


# ═══════════════════════════════════════════════════════════════════
# Search results parser
# ═══════════════════════════════════════════════════════════════════


def _parse_search_results(html: str) -> list[GoogleMapsPlace]:
    """Parse Google Maps search results from rendered HTML."""
    soup = BeautifulSoup(html, "lxml")
    places: list[GoogleMapsPlace] = []

    # Find all place cards
    cards = soup.select("div[role='article'].Nv2PK")
    if not cards:
        cards = soup.select("div.Nv2PK")
    if not cards:
        # Broader fallback
        cards = soup.select("div[role='article']")

    logger.info("Maps search: %d place cards found", len(cards))

    for i, card in enumerate(cards):
        try:
            place = _parse_place_card(card, i + 1)
            if place:
                places.append(place)
        except Exception as e:
            logger.debug("Failed to parse Maps card %d: %s", i, e)

    return places


def _parse_place_card(card, position: int) -> GoogleMapsPlace | None:
    """Parse a single place card from search results."""

    # === Title ===
    title = None
    title_el = card.select_one(".qBF1Pd.fontHeadlineSmall")
    if not title_el:
        title_el = card.select_one(".qBF1Pd")
    if title_el:
        title = title_el.get_text(strip=True)

    if not title:
        # Try aria-label on the card itself
        aria = card.get("aria-label", "")
        if aria:
            title = aria.strip()

    if not title:
        return None

    # Skip sponsored results
    if card.select_one("span.jHLihd"):
        return None

    # === URL + Place ID + CID + Coordinates (from link href) ===
    url = ""
    place_id = None
    cid = None
    latitude = None
    longitude = None

    link_el = card.select_one("a.hfpxzc[href]")
    if link_el:
        url = link_el.get("href", "")

        # Extract CID: 0x....:0x....
        cid_match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", url)
        if cid_match:
            cid = cid_match.group(1)

        # Extract Place ID: !16s{encoded_place_id}
        pid_match = re.search(r"!16s(%2F[^!]+|/[^!]+)", url)
        if pid_match:
            place_id = unquote(pid_match.group(1))

        # Extract coordinates: !3d{lat}!4d{lng}
        lat_match = re.search(r"!3d([\d.-]+)", url)
        lng_match = re.search(r"!4d([\d.-]+)", url)
        if lat_match:
            try:
                latitude = float(lat_match.group(1))
            except ValueError:
                pass
        if lng_match:
            try:
                longitude = float(lng_match.group(1))
            except ValueError:
                pass

    if not url:
        url = f"https://www.google.com/maps/search/{quote_plus(title)}"

    # === Rating + Review Count ===
    rating = None
    review_count = None

    # Try aria-label first (most reliable: "4.7 stars 1,381 Reviews")
    rating_span = card.select_one("span.ZkP5Je[aria-label]")
    if rating_span:
        label = rating_span.get("aria-label", "")
        r_match = re.search(r"([\d.]+)\s*stars?", label, re.I)
        if r_match:
            try:
                rating = float(r_match.group(1))
            except ValueError:
                pass
        rv_match = re.search(r"([\d,]+)\s*Reviews?", label, re.I)
        if rv_match:
            try:
                review_count = int(rv_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # Fallback: direct selectors
    if rating is None:
        r_el = card.select_one(".MW4etd")
        if r_el:
            try:
                rating = float(r_el.get_text(strip=True))
            except ValueError:
                pass

    if review_count is None:
        rc_el = card.select_one(".UY7F9")
        if rc_el:
            text = rc_el.get_text(strip=True).strip("()")
            try:
                review_count = int(text.replace(",", ""))
            except ValueError:
                pass

    # === Price Level ===
    price_level = None
    price_level_text = None

    # Price is in W4Efsd rows — look for $ patterns or price range
    for span in card.select(".W4Efsd span"):
        text = span.get_text(strip=True)
        # Match "$", "$$", "$$$", "$$$$"
        if re.match(r"^\${1,4}$", text):
            price_level_text = text
            price_level = len(text)
            break
        # Match price range like "$50-100"
        if re.match(r"^\$\d+[-–]\d+\+?$", text):
            price_level_text = text
            break
        if re.match(r"^\$\d+\+$", text):
            price_level_text = text
            break

    # === Category / Type ===
    place_type = None
    subtypes = []
    address = None
    description = None
    open_now = None
    hours_text = None

    # Parse W4Efsd rows for category, address, description, hours
    w4_rows = card.select("div.W4Efsd")
    for row in w4_rows:
        text = row.get_text(separator=" · ", strip=True)
        if not text:
            continue

        # Skip the rating/price row
        if row.select_one(".MW4etd") or row.select_one(".ZkP5Je"):
            continue

        spans = row.select(":scope > span, :scope > div.W4Efsd > span")
        span_texts = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]

        for st in span_texts:
            # Category detection (short text, no digits, not a status)
            if (
                not place_type
                and 2 < len(st) < 40
                and not re.search(r"\d", st)
                and st not in ("·", "⋅")
                and "Open" not in st
                and "Close" not in st
            ):
                place_type = st
                if place_type not in subtypes:
                    subtypes.append(place_type)

            # Address detection (has digit, looks like street address)
            if (
                not address
                and re.search(r"\d", st)
                and len(st) > 5
                and not st.startswith("$")
                and not re.match(r"^\d+\.?\d*$", st)
                and "star" not in st.lower()
                and "review" not in st.lower()
            ):
                address = st

            # Open/closed detection
            if "Open" in st or "Closed" in st:
                open_now = "Open" in st
                hours_text = st

        # Description — longer text without digits/special patterns
        inner_text = row.get_text(strip=True)
        if (
            not description
            and len(inner_text) > 20
            and not row.select_one(".MW4etd")
            and "Open" not in inner_text
            and "Close" not in inner_text
            and not re.match(r"^[\d$€£¥]", inner_text)
        ):
            # Could be a description
            if not any(
                inner_text.startswith(s)
                for s in span_texts
                if len(s) < 10
            ):
                description = inner_text

    # === Services (Dine-in, Takeaway, Delivery) ===
    attributes = []
    for svc in card.select(".ah5Ghc"):
        svc_text = svc.get_text(strip=True)
        if svc_text:
            attributes.append(svc_text)

    # Wheelchair accessible
    if card.select_one("span[aria-label*='Wheelchair']"):
        attributes.append("Wheelchair accessible")

    # === Thumbnail ===
    thumbnail = None
    img_el = card.select_one("img[src*='googleusercontent.com']")
    if img_el:
        thumbnail = img_el.get("src")

    # === Action buttons (Reserve, Order) ===
    reservation_url = None
    order_url = None
    for btn in card.select("a.A1zNzb, a.Qmvdpe"):
        btn_text = btn.get_text(strip=True).lower()
        href = btn.get("href", "")
        if "reserve" in btn_text or "book" in btn_text:
            reservation_url = href
        elif "order" in btn_text:
            order_url = href

    return GoogleMapsPlace(
        position=position,
        title=title,
        place_id=place_id,
        cid=cid,
        url=url,
        address=address,
        latitude=latitude,
        longitude=longitude,
        rating=rating,
        review_count=review_count,
        price_level=price_level,
        price_level_text=price_level_text,
        type=place_type,
        subtypes=subtypes if subtypes else None,
        business_status="OPERATIONAL" if open_now else None,
        open_now=open_now,
        thumbnail=thumbnail,
        description=description,
        attributes=attributes if attributes else None,
        reservation_url=reservation_url,
        order_url=order_url,
    )


# ═══════════════════════════════════════════════════════════════════
# Place details parser
# ═══════════════════════════════════════════════════════════════════


def _strip_icons(text: str) -> str:
    """Strip Google icon font characters (Unicode Private Use Area)."""
    return re.sub(r"[\ue000-\uf8ff]", "", text).strip()


def _parse_place_details(
    html: str,
    include_reviews: bool = False,
    reviews_limit: int = 5,
    metadata: dict | None = None,
) -> GoogleMapsPlace | None:
    """Parse a Google Maps place details page."""
    soup = BeautifulSoup(html, "lxml")

    # === Title ===
    title = None
    title_el = soup.select_one("h1.DUwDvf")
    if not title_el:
        title_el = soup.select_one("div[role='main'] h1")
    if title_el:
        title = _strip_icons(title_el.get_text(strip=True))

    if not title:
        return None

    # === Rating ===
    rating = None
    review_count = None

    # aria-label on stars: "4.5 stars"
    stars_el = soup.select_one("span[aria-label*='stars']")
    if stars_el:
        label = stars_el.get("aria-label", "")
        r_match = re.search(r"([\d.]+)\s*stars?", label)
        if r_match:
            try:
                rating = float(r_match.group(1))
            except ValueError:
                pass

    # Fallback: .ceNzKf or .F7nice span
    if rating is None:
        for sel in [".ceNzKf", ".F7nice span", ".fontDisplayLarge"]:
            el = soup.select_one(sel)
            if el:
                try:
                    rating = float(el.get_text(strip=True))
                    break
                except ValueError:
                    continue

    # Review count — try aria-label with count, then .UY7F9
    for btn in soup.select("button[jsaction*='reviews']"):
        label = btn.get("aria-label", "")
        rc_match = re.search(r"([\d,]+)\s*reviews?", label, re.I)
        if rc_match:
            try:
                review_count = int(rc_match.group(1).replace(",", ""))
            except ValueError:
                pass
            break

    if review_count is None:
        rc_el = soup.select_one(".UY7F9")
        if rc_el:
            text = rc_el.get_text(strip=True).strip("()")
            try:
                review_count = int(text.replace(",", ""))
            except ValueError:
                pass

    # === Category ===
    place_type = None
    subtypes = []
    cat_el = soup.select_one("button.DkEaL")
    if cat_el:
        place_type = _strip_icons(cat_el.get_text(strip=True))
        subtypes.append(place_type)

    # Additional categories from jslog category buttons
    for cat_btn in soup.select("button[jsaction*='category']"):
        cat_text = _strip_icons(cat_btn.get_text(strip=True))
        if cat_text and cat_text not in subtypes:
            subtypes.append(cat_text)

    # === Address (data-item-id="address") ===
    address = None
    addr_el = soup.select_one("[data-item-id='address']")
    if addr_el:
        address = _strip_icons(addr_el.get_text(strip=True))

    # === Phone (data-item-id contains "phone") ===
    phone = None
    phone_el = soup.select_one("[data-item-id*='phone']")
    if phone_el:
        raw_phone = _strip_icons(phone_el.get_text(strip=True))
        phone_match = re.search(r"[\d()+\-\s]{7,}", raw_phone)
        if phone_match:
            phone = phone_match.group().strip()

    # === Website (data-item-id="authority") ===
    website = None
    web_el = soup.select_one("[data-item-id='authority']")
    if web_el:
        # The element itself may be an <a> tag, or contain one
        href = web_el.get("href", "")
        if not href:
            a_tag = web_el.select_one("a[href]")
            if a_tag:
                href = a_tag.get("href", "")
        if href:
            # Google may wrap in redirects — extract the actual URL
            redir_match = re.search(r"url=([^&]+)", href)
            if redir_match:
                website = unquote(redir_match.group(1))
            elif href.startswith("http"):
                website = href
        if not website:
            website = _strip_icons(web_el.get_text(strip=True))

    # === Hours (data-item-id="oh") ===
    hours = None
    hours_el = soup.select_one("[data-item-id='oh']")
    if hours_el:
        hours_table = hours_el.select_one("table")
        if hours_table:
            hours = []
            for row in hours_table.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    day = _strip_icons(cells[0].get_text(strip=True))
                    time_text = _strip_icons(cells[1].get_text(strip=True))
                    hours.append({"day": day, "hours": time_text})

    # Check open/closed from hours aria-label
    open_now = None
    if hours_el:
        aria = hours_el.get("aria-label", "")
        if "open" in aria.lower():
            open_now = True
        elif "closed" in aria.lower():
            open_now = False

    # === Plus Code (data-item-id="oloc") ===
    plus_code = None
    oloc_el = soup.select_one("[data-item-id='oloc']")
    if oloc_el:
        plus_code = _strip_icons(oloc_el.get_text(strip=True))

    # === Price Level ===
    price_level = None
    price_level_text = None
    price_el = soup.select_one("span.mgr77e")
    if price_el:
        pt = price_el.get_text(strip=True)
        if re.match(r"^\${1,4}$", pt):
            price_level_text = pt
            price_level = len(pt)

    # === Coordinates ===
    latitude = None
    longitude = None
    _meta = metadata or {}

    # Strategy 1: From JS-extracted metadata (most reliable — from URL bar)
    if "latitude" in _meta and "longitude" in _meta:
        latitude = _meta["latitude"]
        longitude = _meta["longitude"]

    # Strategy 2: @lat,lng in page URLs (skip dummy @0,0)
    if latitude is None:
        for meta_sel in [
            "meta[property='og:url']",
            "link[rel='canonical']",
        ]:
            meta = soup.select_one(meta_sel)
            if meta:
                url_str = meta.get("content", "") or meta.get("href", "")
                coord_match = re.search(r"@([\d.-]+),([\d.-]+)", url_str)
                if coord_match:
                    lat = float(coord_match.group(1))
                    lng = float(coord_match.group(2))
                    if abs(lat) > 0.001 or abs(lng) > 0.001:
                        latitude = lat
                        longitude = lng
                        break

    # Strategy 3: !3d / !4d patterns in any URL on the page
    if latitude is None:
        href_match = re.search(r"!3d([\d.-]+)!4d([\d.-]+)", html)
        if href_match:
            try:
                latitude = float(href_match.group(1))
                longitude = float(href_match.group(2))
            except ValueError:
                pass

    # === Place ID and CID from page ===
    place_id = None
    cid = None

    # Try meta tags
    for meta_sel in ["meta[property='og:url']", "link[rel='canonical']"]:
        meta = soup.select_one(meta_sel)
        if meta:
            meta_url = meta.get("content", "") or meta.get("href", "")
            pid_match = re.search(r"place_id[=:]([A-Za-z0-9_-]+)", meta_url)
            if pid_match:
                place_id = pid_match.group(1)
            cid_match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", meta_url)
            if cid_match:
                cid = cid_match.group(1)

    # Try CID from !1s pattern in page URLs
    if not cid:
        cid_match = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", html)
        if cid_match:
            cid = cid_match.group(1)

    # Try CID from scripts (ludocid)
    if not cid:
        for script in soup.select("script"):
            text = script.string or ""
            ludo_match = re.search(r"ludocid[\\u003d=]+(\d+)", text)
            if ludo_match:
                cid = ludo_match.group(1)
                break

    # === Thumbnail / Photos ===
    thumbnail = None
    photos = []
    for img in soup.select("img[src*='googleusercontent.com']"):
        src = img.get("src", "")
        if src and "streetview" not in src:
            if not thumbnail:
                thumbnail = src
            if src not in photos:
                photos.append(src)

    # === Description ===
    description = None
    desc_el = soup.select_one("div.PYvSYb span")
    if desc_el:
        description = _strip_icons(desc_el.get_text(strip=True))

    # === Attributes / Amenities ===
    attributes = []

    # Collect already-parsed field values to deduplicate
    _parsed_values = {
        v for v in [address, phone, website, plus_code] if v
    }

    for attr_div in soup.select("div.iP2t7d, div.RcCsl"):
        attr_text = _strip_icons(attr_div.get_text(strip=True))
        if not attr_text or len(attr_text) > 80:
            continue
        # Skip if text matches an already-parsed info field
        if any(attr_text in pv or pv in attr_text for pv in _parsed_values):
            continue
        if attr_text not in attributes:
            attributes.append(attr_text)

    # Accessibility labels
    for icon in soup.select("span[aria-label*='accessible']"):
        attr_text = icon.get("aria-label", "").strip()
        if attr_text and attr_text not in attributes:
            attributes.append(attr_text)

    # Service options (dine-in, takeaway, delivery, etc.)
    for svc in soup.select("li.hpLkke span"):
        svc_text = _strip_icons(svc.get_text(strip=True))
        if svc_text and len(svc_text) < 50 and svc_text not in attributes:
            attributes.append(svc_text)

    # === Menu / Order / Reservation links ===
    menu_url = None
    order_url = None
    reservation_url = None

    menu_el = soup.select_one("[data-item-id*='menu']")
    if menu_el:
        a_tag = menu_el.select_one("a[href]")
        menu_url = a_tag.get("href") if a_tag else None

    for a_tag in soup.select("a.ITvuef, a[data-tooltip]"):
        tooltip = a_tag.get("data-tooltip", "").lower()
        href = a_tag.get("href", "")
        if "order" in tooltip:
            order_url = href
        elif "reserv" in tooltip or "book" in tooltip:
            reservation_url = href

    # === Reviews ===
    reviews = None
    if include_reviews:
        reviews = _parse_reviews_from_details(soup, reviews_limit)

    # Build URL
    url = ""
    og_url = soup.select_one("meta[property='og:url']")
    if og_url:
        url = og_url.get("content", "")
    if not url:
        canonical = soup.select_one("link[rel='canonical']")
        if canonical:
            url = canonical.get("href", "")
    if not url:
        url = f"https://www.google.com/maps/search/{quote_plus(title)}"

    return GoogleMapsPlace(
        position=1,
        title=title,
        place_id=place_id,
        cid=cid,
        url=url,
        address=address,
        latitude=latitude,
        longitude=longitude,
        plus_code=plus_code,
        website=website,
        phone=phone,
        rating=rating,
        review_count=review_count,
        price_level=price_level,
        price_level_text=price_level_text,
        type=place_type,
        subtypes=subtypes if subtypes else None,
        open_now=open_now,
        thumbnail=thumbnail,
        photos=photos if photos else None,
        photo_count=len(photos) if photos else None,
        hours=hours,
        description=description,
        attributes=attributes if attributes else None,
        menu_url=menu_url,
        order_url=order_url,
        reservation_url=reservation_url,
        reviews=reviews,
    )


def _parse_reviews_from_details(
    soup: BeautifulSoup, limit: int = 5
) -> list[GoogleMapsReview]:
    """Parse reviews from a place details page."""
    reviews: list[GoogleMapsReview] = []

    # Use jftiEf class to get top-level review containers
    # (data-review-id alone returns nested inner divs too)
    review_els = soup.select("div.jftiEf[data-review-id]")
    if not review_els:
        review_els = soup.select("div.jftiEf")
    if not review_els:
        review_els = soup.select("[data-review-id]")

    for el in review_els[:limit]:
        try:
            # Author name — try aria-label on the container first, then d4r55
            author = None
            container_label = el.get("aria-label", "").strip()
            if container_label:
                author = container_label
            if not author:
                author_el = el.select_one("div.d4r55")
                if author_el:
                    author = author_el.get_text(strip=True)
            if not author:
                # Try the photo button's aria-label
                photo_btn = el.select_one("button.WEBjve[aria-label]")
                if photo_btn:
                    label = photo_btn.get("aria-label", "")
                    # "Photo of John Doe"
                    author = re.sub(r"^Photo of\s+", "", label).strip()
            if not author:
                continue

            # Author URL
            author_url = None
            author_link = el.select_one("a[href*='contrib']")
            if not author_link:
                # Try button with data-href
                btn = el.select_one("button.WEBjve[data-href]")
                if btn:
                    author_url = btn.get("data-href", "")
            if author_link:
                author_url = author_link.get("href", "")

            # Profile photo
            profile_photo = None
            photo_el = el.select_one("img.NBa7we")
            if photo_el:
                profile_photo = photo_el.get("src", "")

            # Rating
            rev_rating = None
            stars_el = el.select_one("span[aria-label*='star']")
            if stars_el:
                label = stars_el.get("aria-label", "")
                rm = re.search(r"(\d+)", label)
                if rm:
                    try:
                        rev_rating = float(rm.group(1))
                    except ValueError:
                        pass

            # Text
            text = None
            text_el = el.select_one("span.wiI7pd")
            if text_el:
                text = text_el.get_text(strip=True)

            # Relative time
            relative_time = None
            time_el = el.select_one("span.rsqaWe")
            if time_el:
                relative_time = time_el.get_text(strip=True)

            reviews.append(
                GoogleMapsReview(
                    author_name=author,
                    author_url=author_url,
                    profile_photo_url=profile_photo,
                    rating=rev_rating,
                    text=text,
                    relative_time=relative_time,
                )
            )
        except Exception as e:
            logger.debug("Failed to parse review: %s", e)

    return reviews


# ═══════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════


async def google_maps(
    query: str | None = None,
    coordinates: str | None = None,
    radius: int | None = None,
    zoom: int | None = None,
    type_filter: str | None = None,
    keyword: str | None = None,
    min_rating: float | None = None,
    open_now: bool = False,
    price_level: int | None = None,
    sort_by: str | None = None,
    num_results: int = 20,
    place_id: str | None = None,
    cid: str | None = None,
    data: str | None = None,
    language: str = "en",
    country: str | None = None,
    include_reviews: bool = False,
    reviews_limit: int = 5,
    reviews_sort: str = "most_relevant",
) -> GoogleMapsResponse:
    """Search Google Maps or get place details.

    If place_id, cid, or data is provided → place details mode.
    Otherwise → search mode with optional coordinates and filters.
    Results cached in Redis for 5 minutes.
    """
    start = time.time()
    is_detail_mode = bool(place_id or cid or data)

    # Determine search type
    search_type = "place_details" if is_detail_mode else "search"
    if not is_detail_mode and coordinates and not query:
        search_type = "nearby"

    # Check Redis cache
    key = _cache_key(query, coordinates, place_id, cid, num_results, language, type_filter)
    try:
        from app.core.redis import redis_client

        cached = await redis_client.get(key)
        if cached:
            cached_data = json.loads(cached)
            cached_data["time_taken"] = round(time.time() - start, 3)
            logger.info("Maps cache hit for '%s'", query or place_id or cid)
            return GoogleMapsResponse(**cached_data)
    except Exception:
        pass

    places: list[GoogleMapsPlace] = []

    if is_detail_mode:
        # === Place Details Mode ===
        url = _build_place_url(
            place_id, cid, data, query, language, coordinates=coordinates
        )
        logger.info("Maps place details: %s", url)

        html, meta = await _fetch_maps_details(url)
        if html:
            html_lower = html.lower()
            if "captcha" not in html_lower and "unusual traffic" not in html_lower:
                place = _parse_place_details(
                    html, include_reviews, reviews_limit, metadata=meta
                )
                if place:
                    places.append(place)
            else:
                logger.warning("Google CAPTCHA detected during Maps details fetch")
    else:
        # === Search Mode ===
        if not query and not coordinates:
            return GoogleMapsResponse(
                success=False,
                query=query,
                search_type=search_type,
                time_taken=round(time.time() - start, 3),
            )

        # Build search query
        search_query = query or ""
        if keyword:
            search_query = f"{search_query} {keyword}".strip()
        if not search_query and type_filter:
            search_query = type_filter

        url = _build_search_url(
            search_query, coordinates, radius, zoom, language, type_filter
        )
        logger.info("Maps search: %s", url)

        html = await _fetch_maps_search(url, num_results)
        if html:
            html_lower = html.lower()
            if "captcha" not in html_lower and "unusual traffic" not in html_lower:
                places = _parse_search_results(html)
                logger.info("Maps search: %d places parsed", len(places))

                # Fallback: if no search cards found, Google may have
                # navigated to a single place (e.g. searching a city name).
                # Try parsing the page as a place details view.
                if not places:
                    # Extract coords from og:image since the search fetcher
                    # doesn't do JS-based coordinate extraction
                    meta: dict = {}
                    og = BeautifulSoup(html, "lxml").select_one(
                        "meta[property='og:image']"
                    )
                    if og:
                        c = og.get("content", "")
                        cm = re.search(r"center=([\d.-]+)%2C([\d.-]+)", c)
                        if cm:
                            try:
                                meta["latitude"] = float(cm.group(1))
                                meta["longitude"] = float(cm.group(2))
                            except ValueError:
                                pass

                    place = _parse_place_details(
                        html, include_reviews, reviews_limit, metadata=meta
                    )
                    if place:
                        places.append(place)
                        search_type = "place_details"
                        logger.info(
                            "Maps fallback: parsed as place details '%s'",
                            place.title,
                        )
            else:
                logger.warning("Google CAPTCHA detected during Maps search")

    # === Post-processing: apply client-side filters ===
    if places and not is_detail_mode:
        if min_rating:
            places = [p for p in places if p.rating and p.rating >= min_rating]

        if open_now:
            places = [p for p in places if p.open_now is True]

        if price_level:
            places = [
                p for p in places
                if p.price_level and p.price_level <= price_level
            ]

        # Sort
        if sort_by == "rating":
            places.sort(key=lambda p: p.rating or 0, reverse=True)
        elif sort_by == "reviews":
            places.sort(key=lambda p: p.review_count or 0, reverse=True)

        # Re-number positions after filtering/sorting
        for i, p in enumerate(places):
            p.position = i + 1

        # Trim to requested count
        places = places[:num_results]

    # === Build response ===
    elapsed = round(time.time() - start, 3)

    if not places:
        return GoogleMapsResponse(
            success=False,
            query=query,
            coordinates_used=coordinates,
            search_type=search_type,
            time_taken=elapsed,
        )

    # Filters echo
    filters_applied: dict[str, str | float | bool] = {}
    if type_filter:
        filters_applied["type"] = type_filter
    if min_rating:
        filters_applied["min_rating"] = min_rating
    if open_now:
        filters_applied["open_now"] = True
    if price_level:
        filters_applied["price_level"] = float(price_level)
    if sort_by:
        filters_applied["sort_by"] = sort_by

    result = GoogleMapsResponse(
        query=query,
        coordinates_used=coordinates,
        search_type=search_type,
        time_taken=elapsed,
        filters_applied=filters_applied if filters_applied else None,
        places=places,
    )

    # Cache
    try:
        from app.core.redis import redis_client

        cache_data = result.model_dump()
        await redis_client.set(key, json.dumps(cache_data), ex=_CACHE_TTL)
    except Exception:
        pass

    return result
