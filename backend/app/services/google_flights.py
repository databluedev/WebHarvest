"""Google Flights scraper — HTTP-only with protobuf URL encoding.

Strategy chain:
1. curl_cffi with Chrome TLS impersonation (fastest, HTTP-only)
2. httpx fallback (if curl_cffi unavailable)
3. nodriver (real browser, bypasses CAPTCHA)

The Google Flights ?tfs= parameter is a base64-encoded protobuf blob
containing flight search parameters. We encode it from scratch using raw
protobuf wire format — no .proto compilation needed.

Results are cached in Redis for 5 minutes.
"""

import base64
import hashlib
import logging
import re
import time

import httpx

from app.config import settings
from app.schemas.data_google import (
    GoogleFlightsListing,
    GoogleFlightsRequest,
    GoogleFlightsResponse,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes

_GOOGLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ═══════════════════════════════════════════════════════════════════
#  Protobuf encoder — raw wire format, no .proto compilation
# ═══════════════════════════════════════════════════════════════════

_SEAT_MAP = {
    "economy": 1,
    "premium_economy": 2,
    "business": 3,
    "first": 4,
}

_TRIP_MAP = {
    "round_trip": 1,
    "one_way": 2,
}

_PASSENGER_MAP = {
    "adult": 1,
    "child": 2,
    "infant_in_seat": 3,
    "infant_on_lap": 4,
}


def _encode_varint(value: int) -> bytes:
    """Encode an integer as a protobuf varint."""
    parts = []
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value & 0x7F)
    return bytes(parts)


def _encode_tag(field_number: int, wire_type: int) -> bytes:
    """Encode a protobuf field tag."""
    return _encode_varint((field_number << 3) | wire_type)


def _encode_string(field_number: int, value: str) -> bytes:
    """Encode a string field (wire type 2 = length-delimited)."""
    data = value.encode("utf-8")
    return _encode_tag(field_number, 2) + _encode_varint(len(data)) + data


def _encode_varint_field(field_number: int, value: int) -> bytes:
    """Encode a varint field (wire type 0)."""
    return _encode_tag(field_number, 0) + _encode_varint(value)


def _encode_message(field_number: int, data: bytes) -> bytes:
    """Encode a nested message field (wire type 2)."""
    return _encode_tag(field_number, 2) + _encode_varint(len(data)) + data


def _encode_airport(field_number: int, iata_code: str) -> bytes:
    """Encode an Airport message: { field 2 (string) = IATA code }."""
    inner = _encode_string(2, iata_code)
    return _encode_message(field_number, inner)


def _encode_flight_data(
    date: str,
    origin: str,
    destination: str,
    max_stops: int | None = None,
) -> bytes:
    """Encode a FlightData message.

    FlightData {
        string date = 2;
        int32 max_stops = 5;      // optional
        Airport from_flight = 13;
        Airport to_flight = 14;
    }
    """
    data = _encode_string(2, date)
    if max_stops is not None:
        data += _encode_varint_field(5, max_stops)
    data += _encode_airport(13, origin)
    data += _encode_airport(14, destination)
    return data


def encode_tfs(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    seat: str = "economy",
    trip: str | None = None,
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    max_stops: int | None = None,
) -> str:
    """Encode flight search parameters into a base64 ?tfs= blob.

    Returns the base64-encoded string (no padding, URL-safe).
    """
    # Auto-detect trip type
    if trip is None:
        trip = "round_trip" if return_date else "one_way"

    # Build the Info message
    body = b""

    # Field 3 (repeated): flight data legs
    # Outbound leg
    outbound = _encode_flight_data(departure_date, origin, destination, max_stops)
    body += _encode_message(3, outbound)

    # Return leg (if round trip)
    if return_date and trip == "round_trip":
        ret = _encode_flight_data(return_date, destination, origin, max_stops)
        body += _encode_message(3, ret)

    # Field 8 (repeated varint): passengers
    for _ in range(adults):
        body += _encode_varint_field(8, _PASSENGER_MAP["adult"])
    for _ in range(children):
        body += _encode_varint_field(8, _PASSENGER_MAP["child"])
    for _ in range(infants_in_seat):
        body += _encode_varint_field(8, _PASSENGER_MAP["infant_in_seat"])
    for _ in range(infants_on_lap):
        body += _encode_varint_field(8, _PASSENGER_MAP["infant_on_lap"])

    # Field 9 (varint): seat class
    body += _encode_varint_field(9, _SEAT_MAP.get(seat, 1))

    # Field 19 (varint): trip type
    body += _encode_varint_field(19, _TRIP_MAP.get(trip, 1))

    # Base64url encode (no padding)
    encoded = base64.urlsafe_b64encode(body).rstrip(b"=")
    return encoded.decode("ascii")


# ═══════════════════════════════════════════════════════════════════
#  Cache
# ═══════════════════════════════════════════════════════════════════


def _cache_key(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    seat: str,
    adults: int,
    max_stops: int | None,
) -> str:
    raw = (
        f"flights:{origin}|{destination}|{departure_date}"
        f"|{return_date or ''}|{seat}|{adults}|{max_stops or ''}"
    )
    h = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f"serp:flights:{h}"


# ═══════════════════════════════════════════════════════════════════
#  URL builder
# ═══════════════════════════════════════════════════════════════════


def _build_url(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    seat: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    max_stops: int | None = None,
    language: str = "en",
    currency: str | None = None,
) -> str:
    """Build a Google Flights search URL with encoded tfs parameter."""
    tfs = encode_tfs(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        seat=seat,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        max_stops=max_stops,
    )

    params = f"tfs={tfs}&hl={language}&tfu=EgQIABABIgA"
    if currency:
        params += f"&curr={currency}"

    return f"https://www.google.com/travel/flights?{params}"


# ═══════════════════════════════════════════════════════════════════
#  HTTP fetchers
# ═══════════════════════════════════════════════════════════════════


async def _fetch_via_curl_cffi(url: str) -> str | None:
    """Fetch with curl_cffi — best TLS fingerprint for Google."""
    try:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                headers=_GOOGLE_HEADERS,
                timeout=20,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"Google Flights curl_cffi returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"curl_cffi Google Flights fetch failed: {e}")
    return None


async def _fetch_via_httpx(url: str) -> str | None:
    """Fetch with httpx — fallback if curl_cffi unavailable."""
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=_GOOGLE_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning(f"httpx Google Flights fetch failed: {e}")
    return None


async def _fetch_via_nodriver(url: str) -> str | None:
    """Fetch with nodriver — real browser, bypasses CAPTCHA."""
    try:
        from app.services.nodriver_helper import fetch_page_nodriver

        html = await fetch_page_nodriver(
            url,
            wait_selector="ul.Rk10dc",
            timeout=25,
        )
        return html
    except Exception as e:
        logger.warning(f"nodriver Google Flights fetch failed: {e}")
    return None


async def _fetch_html(url: str) -> str | None:
    """Try all strategies in order: curl_cffi → httpx → nodriver."""
    html = await _fetch_via_curl_cffi(url)
    if html and "AF_initDataCallback" in html:
        return html

    html = await _fetch_via_httpx(url)
    if html and "AF_initDataCallback" in html:
        return html

    html = await _fetch_via_nodriver(url)
    if html:
        return html

    return None


# ═══════════════════════════════════════════════════════════════════
#  AF_initDataCallback JSON parser — reverse-engineered field indices
# ═══════════════════════════════════════════════════════════════════
#
# Google Flights embeds flight data in AF_initDataCallback({key:'ds:1', data:...})
# inside the SSR HTML. The data is a deeply nested JSON array.
#
# Top-level data structure (ds:1):
#   [1]  — Airport info (origin)
#   [2]  — "Best flights" offers
#   [3]  — "Other departing flights" offers
#   [11] — Airline metadata
#   [17] — Airport info (destination / return)
#
# Each offer section: [offer_list, null, int, int, list]
#   offer_list[N] = single offer (list[11])
#
# Single offer structure (list[11]):
#   [0] — Flight segment details (list[25])
#   [1] — Pricing: [[null, price_value], booking_token]
#   [3] — Best indicator (1 = best)
#   [5] — Emissions data [co2_outbound, co2_return, co2_total]
#   [8] — Booking payload (base64 JSON)
#
# Flight segment [offer][0] (list[25]):
#   [0]  — Airline IATA code ("6E", "AI", "SG")
#   [1]  — Airline name list (["IndiGo"])
#   [2]  — Route legs (list of leg details, has aircraft/flight num)
#   [3]  — Origin IATA code
#   [4]  — Departure date [year, month, day]
#   [5]  — Departure time [hour, minute]
#   [6]  — Destination IATA code
#   [7]  — Arrival date [year, month, day]
#   [8]  — Arrival time [hour, minute]
#   [9]  — Duration in minutes
#   [12] — Number of stops
#   [22] — Extended price/emissions data
#   [24] — Airline accessibility info
#
# Route leg [offer][0][2][N]:
#   [3]  — Leg origin IATA
#   [4]  — Leg origin airport name
#   [5]  — Leg destination airport name
#   [6]  — Leg destination IATA
#   [11] — Leg duration minutes
#   [13] — Cabin class code
#   [14] — Seat pitch ("28 in")
#   [17] — Aircraft type ("Airbus A321neo")
#   [22] — [airline_code, flight_number, null, airline_name]


def _safe_get(data: list | None, idx: int, default=None):
    """Safely index into a list."""
    if data is None or not isinstance(data, list):
        return default
    if idx < 0 or idx >= len(data):
        return default
    val = data[idx]
    return val if val is not None else default


def _format_time(time_arr: list | None) -> str:
    """Convert [hour, minute] to '7:05 AM' format."""
    if not time_arr or not isinstance(time_arr, list) or len(time_arr) < 2:
        return ""
    h, m = time_arr[0], time_arr[1]
    if h is None or m is None:
        return ""
    period = "AM" if h < 12 else "PM"
    display_h = h if h <= 12 else h - 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{m:02d} {period}"


def _format_duration(minutes: int | None) -> str:
    """Convert minutes to 'Xhr Ymin' format."""
    if minutes is None:
        return ""
    h, m = divmod(minutes, 60)
    if h > 0 and m > 0:
        return f"{h} hr {m} min"
    elif h > 0:
        return f"{h} hr"
    else:
        return f"{m} min"


def _arrival_day_offset(dep_date: list | None, arr_date: list | None) -> str | None:
    """Calculate day offset like '+1' for next-day arrival."""
    if not dep_date or not arr_date:
        return None
    if len(dep_date) < 3 or len(arr_date) < 3:
        return None
    from datetime import date
    try:
        d1 = date(dep_date[0], dep_date[1], dep_date[2])
        d2 = date(arr_date[0], arr_date[1], arr_date[2])
        diff = (d2 - d1).days
        if diff > 0:
            return f"+{diff}"
        elif diff < 0:
            return str(diff)
    except (ValueError, TypeError):
        pass
    return None


def _extract_af_data(html: str) -> list | None:
    """Extract the ds:1 data from AF_initDataCallback in the HTML."""
    import json as _json

    # Find all AF_initDataCallback blocks
    for match in re.finditer(
        r"AF_initDataCallback\(\{.*?key:\s*'(ds:\d+)'.*?data:\s*",
        html,
        re.DOTALL,
    ):
        key = match.group(1)
        if key != "ds:1":
            continue

        # Find the JSON data after "data:"
        start = match.end()
        # Walk through to find balanced JSON
        depth = 0
        i = start
        json_start = None
        while i < len(html):
            c = html[i]
            if c == "[" or c == "{":
                if json_start is None:
                    json_start = i
                depth += 1
            elif c == "]" or c == "}":
                depth -= 1
                if depth == 0 and json_start is not None:
                    try:
                        return _json.loads(html[json_start : i + 1])
                    except _json.JSONDecodeError:
                        pass
                    json_start = None
            elif c == '"':
                # Skip string content
                i += 1
                while i < len(html) and html[i] != '"':
                    if html[i] == "\\":
                        i += 1  # skip escaped char
                    i += 1
            i += 1

    return None


def _parse_offer(
    offer: list,
    position: int,
    is_best: bool,
    currency: str | None,
) -> GoogleFlightsListing | None:
    """Parse a single flight offer from the AF_initDataCallback JSON."""
    if not isinstance(offer, list) or len(offer) < 2:
        return None

    flight = offer[0]
    if not isinstance(flight, list) or len(flight) < 13:
        return None

    # Basic flight info
    airline_code = _safe_get(flight, 0, "")
    airline_names = _safe_get(flight, 1, [])
    airline_name = airline_names[0] if isinstance(airline_names, list) and airline_names else airline_code

    origin = _safe_get(flight, 3, "")
    dep_date = _safe_get(flight, 4)
    dep_time = _safe_get(flight, 5)
    dest = _safe_get(flight, 6, "")
    arr_date = _safe_get(flight, 7)
    arr_time = _safe_get(flight, 8)
    duration_min = _safe_get(flight, 9)
    stops = _safe_get(flight, 12, 0)

    # Price from offer[1][0][1]
    price_value = None
    pricing = _safe_get(offer, 1)
    if isinstance(pricing, list) and len(pricing) >= 1:
        price_inner = _safe_get(pricing, 0)
        if isinstance(price_inner, list) and len(price_inner) >= 2:
            price_value = price_inner[1]

    # Flight number and aircraft from route legs
    flight_number = None
    aircraft = None
    layover_airports = []
    legs = _safe_get(flight, 2, [])
    if isinstance(legs, list):
        for leg in legs:
            if not isinstance(leg, list):
                continue
            # Extract flight number from leg[22]
            leg_info = _safe_get(leg, 22)
            if isinstance(leg_info, list) and len(leg_info) >= 2:
                code = _safe_get(leg_info, 0, "")
                num = _safe_get(leg_info, 1, "")
                if code and num:
                    flight_number = f"{code} {num}"

            # Aircraft type from leg[17]
            ac = _safe_get(leg, 17)
            if ac and isinstance(ac, str):
                aircraft = ac

        # Layover airports (for multi-leg flights)
        if len(legs) > 1:
            for leg in legs[:-1]:
                if isinstance(leg, list):
                    lay_dest = _safe_get(leg, 6, "")
                    if lay_dest:
                        layover_airports.append(lay_dest)

    # Emissions data from offer[5]
    emissions = None
    emissions_data = _safe_get(offer, 5)
    if isinstance(emissions_data, list) and len(emissions_data) >= 1:
        co2 = _safe_get(emissions_data, 0)
        if co2 and isinstance(co2, (int, float)) and co2 > 0:
            emissions = f"{co2} kg CO₂"

    # Format display values
    dep_time_str = _format_time(dep_time)
    arr_time_str = _format_time(arr_time)
    duration_str = _format_duration(duration_min)
    day_offset = _arrival_day_offset(dep_date, arr_date)

    # Price formatting
    price_display = None
    if price_value is not None:
        sym = currency or ""
        if sym:
            price_display = f"{sym} {price_value:,.0f}" if isinstance(price_value, (int, float)) else str(price_value)
        else:
            price_display = f"{price_value:,.0f}" if isinstance(price_value, (int, float)) else str(price_value)

    stops_text = "Nonstop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"

    return GoogleFlightsListing(
        position=position,
        is_best=is_best,
        airline=airline_name,
        airline_logo_url=None,
        flight_number=flight_number,
        departure_time=dep_time_str,
        arrival_time=arr_time_str,
        arrival_time_ahead=day_offset,
        duration=duration_str,
        duration_minutes=duration_min,
        stops=stops,
        stops_text=stops_text,
        layover_airports=layover_airports or None,
        price=price_display,
        price_value=float(price_value) if price_value is not None else None,
        currency_symbol=currency,
        origin=origin,
        destination=dest,
        aircraft=aircraft,
        emissions=emissions,
    )


def _parse_flights_from_json(
    data: list,
    currency: str | None = None,
) -> tuple[list[GoogleFlightsListing], str | None]:
    """Parse all flight offers from ds:1 JSON data.

    Returns (flights_list, price_trend).
    """
    flights: list[GoogleFlightsListing] = []
    position = 0

    # data[2] = best flights, data[3] = other flights
    for section_idx, section_key in enumerate([2, 3]):
        is_best = section_idx == 0
        label = "best" if is_best else "other"
        section = _safe_get(data, section_key)
        if not isinstance(section, list) or len(section) < 1:
            logger.debug("Flights section data[%d] (%s): empty or None", section_key, label)
            continue

        offer_list = _safe_get(section, 0)
        if not isinstance(offer_list, list):
            logger.debug("Flights section data[%d][0] (%s): not a list", section_key, label)
            continue

        parsed_count = 0
        for offer in offer_list:
            position += 1
            parsed = _parse_offer(offer, position, is_best, currency)
            if parsed:
                flights.append(parsed)
                parsed_count += 1

        logger.debug(
            "Flights %s section: %d offers, %d parsed",
            label, len(offer_list), parsed_count,
        )

    # Price trend from data[7] or other indices (not always present)
    price_trend = None

    return flights, price_trend


# ═══════════════════════════════════════════════════════════════════
#  Main service function
# ═══════════════════════════════════════════════════════════════════


async def google_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    seat: str = "economy",
    max_stops: int | None = None,
    language: str = "en",
    currency: str | None = None,
    country: str | None = None,
) -> GoogleFlightsResponse:
    """Search Google Flights and return structured flight data."""
    from datetime import date as _date

    # Normalize IATA codes
    origin = origin.strip().upper()
    destination = destination.strip().upper()

    # Validate IATA codes (must be exactly 3 letters)
    if not origin.isalpha() or len(origin) != 3:
        return GoogleFlightsResponse(
            success=False, origin=origin, destination=destination,
            departure_date=departure_date, return_date=return_date,
            trip_type="round_trip" if return_date else "one_way",
            adults=adults, seat=seat, time_taken=0, flights=[],
            error=f"Invalid origin airport code: '{origin}'. Must be a 3-letter IATA code (e.g. MAA, JFK).",
        )
    if not destination.isalpha() or len(destination) != 3:
        return GoogleFlightsResponse(
            success=False, origin=origin, destination=destination,
            departure_date=departure_date, return_date=return_date,
            trip_type="round_trip" if return_date else "one_way",
            adults=adults, seat=seat, time_taken=0, flights=[],
            error=f"Invalid destination airport code: '{destination}'. Must be a 3-letter IATA code (e.g. BLR, LAX).",
        )

    # Validate departure date is not in the past
    try:
        dep = _date.fromisoformat(departure_date)
        today = _date.today()
        if dep < today:
            return GoogleFlightsResponse(
                success=False, origin=origin, destination=destination,
                departure_date=departure_date, return_date=return_date,
                trip_type="round_trip" if return_date else "one_way",
                adults=adults, seat=seat, time_taken=0, flights=[],
                error=f"Departure date {departure_date} is in the past. Use a future date.",
            )
    except ValueError:
        return GoogleFlightsResponse(
            success=False, origin=origin, destination=destination,
            departure_date=departure_date, return_date=return_date,
            trip_type="round_trip" if return_date else "one_way",
            adults=adults, seat=seat, time_taken=0, flights=[],
            error=f"Invalid departure date format: '{departure_date}'. Use YYYY-MM-DD.",
        )

    # Validate return date if provided
    if return_date:
        try:
            ret = _date.fromisoformat(return_date)
            if ret < dep:
                return GoogleFlightsResponse(
                    success=False, origin=origin, destination=destination,
                    departure_date=departure_date, return_date=return_date,
                    trip_type="round_trip", adults=adults, seat=seat,
                    time_taken=0, flights=[],
                    error=f"Return date {return_date} is before departure date {departure_date}.",
                )
        except ValueError:
            return GoogleFlightsResponse(
                success=False, origin=origin, destination=destination,
                departure_date=departure_date, return_date=return_date,
                trip_type="round_trip", adults=adults, seat=seat,
                time_taken=0, flights=[],
                error=f"Invalid return date format: '{return_date}'. Use YYYY-MM-DD.",
            )

    # Cache check
    cache_key = _cache_key(
        origin, destination, departure_date, return_date, seat, adults, max_stops
    )
    try:
        from app.core.cache import get_cached_response

        cached = await get_cached_response(cache_key)
        if cached:
            logger.info("Flights cache hit: %s → %s", origin, destination)
            return GoogleFlightsResponse(**cached)
    except Exception:
        pass  # Cache miss or unavailable

    start = time.time()

    # Build URL
    url = _build_url(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        seat=seat,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        max_stops=max_stops,
        language=language,
        currency=currency,
    )

    logger.info("Google Flights URL: %s", url)

    # Fetch HTML
    html = await _fetch_html(url)

    if not html:
        elapsed = time.time() - start
        logger.error("All Google Flights fetch strategies failed")
        return GoogleFlightsResponse(
            success=False,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            trip_type="round_trip" if return_date else "one_way",
            adults=adults,
            seat=seat,
            time_taken=round(elapsed, 3),
            flights=[],
        )

    # Parse flights from AF_initDataCallback JSON (primary strategy)
    flights: list[GoogleFlightsListing] = []
    price_trend = None

    af_data = _extract_af_data(html)
    if af_data:
        flights, price_trend = _parse_flights_from_json(af_data, currency=currency)
        logger.info(
            "Parsed %d flights from AF_initDataCallback JSON", len(flights)
        )
    else:
        logger.warning("AF_initDataCallback not found in response")

    elapsed = time.time() - start

    result = GoogleFlightsResponse(
        success=bool(flights),
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        trip_type="round_trip" if return_date else "one_way",
        adults=adults,
        seat=seat,
        time_taken=round(elapsed, 3),
        total_results=len(flights),
        price_trend=price_trend,
        flights=flights,
        search_url=url,
    )

    # Cache result
    try:
        from app.core.cache import set_cached_response

        await set_cached_response(cache_key, result.model_dump(), _CACHE_TTL)
    except Exception:
        pass

    return result
