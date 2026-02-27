"""Test Google Finance quote — live fetch + parse for multiple tickers."""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")

from app.services.google_finance import google_finance_quote

TICKERS = [
    "AAPL:NASDAQ",
    "GOOGL:NASDAQ",
    "BTC-USD",
    "RELIANCE:NSE",
    "TSLA:NASDAQ",
    "EUR-USD",
]


async def test_one(ticker: str) -> dict:
    t0 = time.time()
    result = await google_finance_quote(ticker, language="en")
    elapsed = time.time() - t0

    print(f"\n{'─' * 60}")
    print(f"  {ticker}")
    print(f"{'─' * 60}")

    if not result.success:
        print(f"  ERROR: {result.error}")
        return {"ticker": ticker, "success": False, "time": elapsed, "error": result.error}

    print(f"  Name:           {result.name}")
    print(f"  Price:          {result.price}")
    if result.price_movement:
        pm = result.price_movement
        print(f"  Change:         {pm.value}  ({pm.percentage})  [{pm.movement}]")
    print(f"  Prev close:     {result.previous_close}")
    print(f"  Currency:       {result.currency}")
    if result.after_hours_price:
        print(f"  After-hours:    {result.after_hours_price}")
        if result.after_hours_movement:
            ah = result.after_hours_movement
            print(f"  AH change:      {ah.value}  ({ah.percentage})  [{ah.movement}]")
    print(f"  Similar stocks: {len(result.similar_stocks or [])}")
    if result.similar_stocks:
        for s in result.similar_stocks[:5]:
            print(f"    {s.stock:<20} {s.name:<30} {s.price}")
    print(f"  News articles:  {len(result.news or [])}")
    if result.news:
        for a in result.news[:3]:
            print(f"    [{a.source or '?':<15}] {a.title[:55]}...")
    print(f"  Fetch time:     {elapsed:.3f}s")

    return {
        "ticker": ticker,
        "success": True,
        "time": elapsed,
        "name": result.name,
        "price": result.price,
        "similar": len(result.similar_stocks or []),
        "news": len(result.news or []),
    }


async def main():
    print("=" * 70)
    print("GOOGLE FINANCE — QUOTE TEST")
    print("=" * 70)

    total_start = time.time()
    results = []

    for ticker in TICKERS:
        r = await test_one(ticker)
        results.append(r)

    total_time = time.time() - total_start

    # ── Summary table ──
    print(f"\n\n{'=' * 70}")
    print(f"{'TICKER':<20} {'STATUS':<8} {'TIME':>6}  {'PRICE':>15}  {'SIMILAR':>7}  {'NEWS':>4}")
    print(f"{'─' * 70}")
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        t = f"{r['time']:.2f}s"
        price = r.get("price", "—") or "—"
        sim = str(r.get("similar", "—"))
        news = str(r.get("news", "—"))
        print(f"  {r['ticker']:<18} {status:<8} {t:>6}  {price:>15}  {sim:>7}  {news:>4}")

    ok = sum(1 for r in results if r["success"])
    avg = sum(r["time"] for r in results) / len(results)
    print(f"{'─' * 70}")
    print(f"  {ok}/{len(results)} passed  |  avg {avg:.2f}s/query  |  total {total_time:.2f}s (sequential)")
    print(f"{'=' * 70}")

    # ── Full JSON for first ticker ──
    print(f"\n── FULL JSON: {TICKERS[0]} ──")
    result = await google_finance_quote(TICKERS[0], language="en")
    out = result.model_dump(exclude_none=True)
    if "similar_stocks" in out:
        out["similar_stocks"] = out["similar_stocks"][:3]
    if "news" in out:
        out["news"] = out["news"][:2]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
