"""Test Google Images scraper — direct HTTP, no browser."""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from app.services.google_images import google_images


async def main():
    print("=" * 70)
    print("  GOOGLE IMAGES SCRAPER TEST")
    print("=" * 70)

    # Test 1: Basic search
    print("\n--- Test 1: Basic search 'hinata' ---")
    t0 = time.time()
    result = await google_images(query="hinata", num_results=100)
    t1 = time.time()

    print(f"  Success: {result.success}")
    print(f"  Images:  {len(result.images)}")
    print(f"  Time:    {t1 - t0:.2f}s")

    if result.images:
        print(f"\n  First 10 results:")
        for img in result.images[:10]:
            print(f"  [{img.position}] {img.title[:60]}")
            print(f"      Image: {img.image_url[:80]}...")
            print(f"      Size:  {img.image_width}x{img.image_height} | {img.file_size or 'N/A'}")
            print(f"      From:  {img.domain or 'N/A'} ({img.site_name or 'N/A'})")
            print(f"      Source: {img.url[:80]}")
            if img.dominant_color:
                print(f"      Color: {img.dominant_color}")
            print()

    # Test 2: With filters
    print("\n--- Test 2: 'sunset' with colour=orange, size=large ---")
    t0 = time.time()
    result2 = await google_images(
        query="sunset", num_results=20,
        colour="orange", size="large",
    )
    t1 = time.time()

    print(f"  Success: {result2.success}")
    print(f"  Images:  {len(result2.images)}")
    print(f"  Time:    {t1 - t0:.2f}s")

    if result2.images:
        for img in result2.images[:5]:
            print(f"  [{img.position}] {img.title[:60]}")
            print(f"      {img.image_width}x{img.image_height} | {img.domain}")
            print()

    # Test 3: Safe search + type
    print("\n--- Test 3: 'cat' with type=photo, safe_search=True ---")
    t0 = time.time()
    result3 = await google_images(
        query="cat", num_results=10,
        type_filter="photo", safe_search=True,
    )
    t1 = time.time()

    print(f"  Success: {result3.success}")
    print(f"  Images:  {len(result3.images)}")
    print(f"  Time:    {t1 - t0:.2f}s")

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Test 1 (basic):    {len(result.images)} images in {result.time_taken}s")
    print(f"  Test 2 (filters):  {len(result2.images)} images in {result2.time_taken}s")
    print(f"  Test 3 (safe+type):{len(result3.images)} images in {result3.time_taken}s")
    print(f"  Method: Pure HTTP (no browser)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
