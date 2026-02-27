"""Tests for Google Flights scraper — protobuf encoder + AF_initDataCallback parser."""

import sys
sys.path.insert(0, ".")

from app.services.google_flights import (
    encode_tfs,
    _build_url,
    _extract_af_data,
    _parse_flights_from_json,
    _format_time,
    _format_duration,
    _arrival_day_offset,
    _safe_get,
)


def test_encode_tfs_round_trip():
    """Round-trip: MAA → BLR, 2026-03-09 to 2026-03-20."""
    tfs = encode_tfs(
        origin="MAA",
        destination="BLR",
        departure_date="2026-03-09",
        return_date="2026-03-20",
        seat="economy",
        adults=1,
    )
    assert tfs
    import re, base64
    assert re.match(r"^[A-Za-z0-9_-]+$", tfs)
    # Verify contents
    padded = tfs + "=" * (4 - len(tfs) % 4) if len(tfs) % 4 else tfs
    raw = base64.urlsafe_b64decode(padded)
    assert b"MAA" in raw
    assert b"BLR" in raw
    assert b"2026-03-09" in raw
    assert b"2026-03-20" in raw
    print(f"  round-trip tfs OK ({len(tfs)} chars)")


def test_encode_tfs_one_way():
    """One-way: JFK → LAX, 2026-04-15, business class, 2 adults + 1 child."""
    tfs = encode_tfs(
        origin="JFK",
        destination="LAX",
        departure_date="2026-04-15",
        seat="business",
        adults=2,
        children=1,
    )
    import base64
    padded = tfs + "=" * (4 - len(tfs) % 4) if len(tfs) % 4 else tfs
    raw = base64.urlsafe_b64decode(padded)
    assert b"JFK" in raw
    assert b"LAX" in raw
    assert b"2026-04-15" in raw
    # Only one date (no return)
    assert raw.count(b"2026-04-15") == 1
    print(f"  one-way tfs OK ({len(tfs)} chars)")


def test_encode_tfs_max_stops():
    """Nonstop-only filter."""
    tfs = encode_tfs(
        origin="SFO",
        destination="LHR",
        departure_date="2026-06-01",
        seat="first",
        adults=1,
        max_stops=0,
    )
    assert tfs
    print(f"  nonstop tfs OK")


def test_build_url():
    url = _build_url(
        origin="MAA",
        destination="BLR",
        departure_date="2026-03-09",
        return_date="2026-03-20",
        currency="INR",
    )
    assert "google.com/travel/flights" in url
    assert "tfs=" in url
    assert "curr=INR" in url
    assert "hl=en" in url
    print(f"  URL OK")


def test_format_time():
    assert _format_time([7, 5]) == "7:05 AM"
    assert _format_time([13, 30]) == "1:30 PM"
    assert _format_time([0, 0]) == "12:00 AM"
    assert _format_time([12, 0]) == "12:00 PM"
    assert _format_time([23, 59]) == "11:59 PM"
    assert _format_time(None) == ""
    assert _format_time([]) == ""
    print("  time formatting OK")


def test_format_duration():
    assert _format_duration(60) == "1 hr"
    assert _format_duration(65) == "1 hr 5 min"
    assert _format_duration(135) == "2 hr 15 min"
    assert _format_duration(30) == "30 min"
    assert _format_duration(None) == ""
    print("  duration formatting OK")


def test_arrival_day_offset():
    assert _arrival_day_offset([2026, 3, 9], [2026, 3, 9]) is None
    assert _arrival_day_offset([2026, 3, 9], [2026, 3, 10]) == "+1"
    assert _arrival_day_offset([2026, 3, 9], [2026, 3, 11]) == "+2"
    assert _arrival_day_offset(None, None) is None
    print("  day offset OK")


def test_safe_get():
    assert _safe_get([1, 2, 3], 0) == 1
    assert _safe_get([1, 2, 3], 5) is None
    assert _safe_get([1, None, 3], 1, "default") == "default"
    assert _safe_get(None, 0) is None
    print("  safe_get OK")


def test_extract_af_data():
    """Test AF_initDataCallback extraction with mock HTML."""
    html = """
    <html><script>
    AF_initDataCallback({key: 'ds:0', data:[1,2,3]});
    AF_initDataCallback({key: 'ds:1', data:["test", [1,2], null, [3,4]]});
    </script></html>
    """
    data = _extract_af_data(html)
    assert data is not None
    assert data[0] == "test"
    assert data[1] == [1, 2]
    assert data[2] is None
    assert data[3] == [3, 4]
    print("  AF_initDataCallback extraction OK")


def test_parse_flights_from_json():
    """Test flight parsing with mock AF_initDataCallback data structure."""
    # Minimal mock of ds:1 structure
    mock_data = [None] * 31

    # data[2] = best flights section
    mock_flight = [
        # [0] = flight details
        [
            "6E",                    # [0] airline code
            ["IndiGo"],              # [1] airline name
            [                        # [2] route legs
                [None, None, None, "MAA", "Chennai Intl", "Kempegowda Intl", "BLR",
                 None, [7, 10], None, [8, 15], 65, [], 2, "28 in", None, 1,
                 "Airbus A321neo", None, 0, [2026, 3, 9], [2026, 3, 9],
                 ["6E", "6081", None, "IndiGo"]],
            ],
            "MAA",                   # [3] origin
            [2026, 3, 9],            # [4] dep date
            [7, 10],                 # [5] dep time
            "BLR",                   # [6] destination
            [2026, 3, 9],            # [7] arr date
            [8, 15],                 # [8] arr time
            65,                      # [9] duration min
            None, None,              # [10,11]
            0,                       # [12] stops
        ],
        # [1] = pricing
        [[None, 6561], "booking_token"],
        None, 1, None, [0, 0, 0],
        None, None, None, None, None,
    ]

    mock_data[2] = [[mock_flight], None, 1, 0, None]
    mock_data[3] = [[], None, 0, 0, None]  # empty other flights

    flights, trend = _parse_flights_from_json(mock_data, currency="₹")
    assert len(flights) == 1
    f = flights[0]
    assert f.airline == "IndiGo"
    assert f.origin == "MAA"
    assert f.destination == "BLR"
    assert f.departure_time == "7:10 AM"
    assert f.arrival_time == "8:15 AM"
    assert f.duration_minutes == 65
    assert f.stops == 0
    assert f.price_value == 6561.0
    assert f.flight_number == "6E 6081"
    assert f.aircraft == "Airbus A321neo"
    assert f.is_best is True
    print(f"  JSON parsing OK: {f.airline} {f.flight_number} {f.departure_time}→{f.arrival_time} ₹{f.price_value:,.0f}")


if __name__ == "__main__":
    tests = [
        test_encode_tfs_round_trip,
        test_encode_tfs_one_way,
        test_encode_tfs_max_stops,
        test_build_url,
        test_format_time,
        test_format_duration,
        test_arrival_day_offset,
        test_safe_get,
        test_extract_af_data,
        test_parse_flights_from_json,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
