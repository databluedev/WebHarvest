"""Test Google Shopping — search and print results."""

import asyncio
import time
from app.services.google_shopping import google_shopping


async def main():
    query = "gaming laptop"
    print(f"Searching Google Shopping for: '{query}'")
    print("=" * 60)

    start = time.time()
    result = await google_shopping(query=query)
    elapsed = time.time() - start

    if not result.success:
        print(f"FAILED — {result.time_taken}s")
        return

    print(f"Got {len(result.products)} products in {elapsed:.1f}s")
    print(f"Total results reported by Google: {result.total_results}")
    print("=" * 60)

    for i, p in enumerate(result.products[:50], 1):
        price = p.price or "N/A"
        rating = f"{p.rating}★" if p.rating else "—"
        reviews = f"({p.review_count} reviews)" if p.review_count else ""
        merchant = p.merchant or "—"
        print(f"{i:3d}. {p.title[:70]}")
        print(f"     {price}  |  {rating} {reviews}  |  {merchant}")
        print()

    if len(result.products) > 50:
        print(f"... and {len(result.products) - 50} more products")

    print("=" * 60)
    print(f"Total unique products: {len(result.products)}")
    print(f"Time: {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
