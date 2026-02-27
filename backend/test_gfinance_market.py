"""Test Google Finance market overview — live fetch + parse."""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")

from app.services.google_finance import google_finance_market


async def main():
    print("=" * 70)
    print("GOOGLE FINANCE — MARKET OVERVIEW TEST")
    print("=" * 70)

    t0 = time.time()
    result = await google_finance_market(language="en")
    elapsed = time.time() - t0

    out = result.model_dump(exclude_none=True)

    # ── Summary ──
    print(f"\nSuccess: {result.success}")
    print(f"Time:    {elapsed:.3f}s (reported: {result.time_taken}s)")
    if result.error:
        print(f"Error:   {result.error}")
        return

    # ── Markets ──
    total_stocks = 0
    for section, stocks in result.markets.items():
        total_stocks += len(stocks)
        print(f"\n── {section} ({len(stocks)} stocks) ──")
        for s in stocks:
            mv = ""
            if s.price_movement:
                mv = f"  {s.price_movement.percentage}  {s.price_movement.value}  [{s.price_movement.movement}]"
            print(f"  {s.stock:<25} {s.name:<40} {s.price:>15}{mv}")

    # ── Trends ──
    if result.market_trends:
        for label, stocks in result.market_trends.items():
            total_stocks += len(stocks)
            print(f"\n── {label.upper()} ({len(stocks)} stocks) ──")
            for s in stocks:
                mv = ""
                if s.price_movement:
                    mv = f"  {s.price_movement.percentage}  [{s.price_movement.movement}]"
                print(f"  {s.stock:<25} {s.name:<40} {s.price:>15}{mv}")

    # ── News ──
    if result.news:
        print(f"\n── NEWS ({len(result.news)} articles) ──")
        for a in result.news:
            src = a.source or "?"
            print(f"  [{src:<20}] {a.title[:70]}")

    # ── Stats ──
    print(f"\n{'=' * 70}")
    print(f"TOTALS: {len(result.markets)} market sections, {total_stocks} stocks, "
          f"{len(result.news or [])} news articles")
    print(f"FETCH + PARSE: {elapsed:.3f}s")
    print(f"{'=' * 70}")

    # ── JSON sample (Futures) ──
    if "Futures" in out.get("markets", {}):
        print("\n── JSON SAMPLE: Futures ──")
        print(json.dumps({"markets": {"Futures": out["markets"]["Futures"]}}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
