"""
Google Finance reverse engineering - Step 2: Test redirect behavior and different URL patterns.
"""
import httpx
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

URLS = [
    # Without /beta
    "https://www.google.com/finance/?hl=en",
    "https://www.google.com/finance/quote/BTC-USD?hl=en",
    "https://www.google.com/finance/quote/AAPL:NASDAQ?hl=en",
    "https://www.google.com/finance/quote/GOOGL:NASDAQ?hl=en",
    # With /beta
    "https://www.google.com/finance/beta?hl=en",
    "https://www.google.com/finance/beta/quote/BTC-USD?hl=en",
    # Markets section
    "https://www.google.com/finance/markets/indexes?hl=en",
    "https://www.google.com/finance/markets/gainers?hl=en",
    "https://www.google.com/finance/markets/losers?hl=en",
]

def main():
    # First, check redirects WITHOUT following them
    client_no_redirect = httpx.Client(headers=HEADERS, follow_redirects=False, timeout=30)
    client_redirect = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30)

    print("=" * 80)
    print("REDIRECT ANALYSIS")
    print("=" * 80)

    for url in URLS:
        try:
            resp = client_no_redirect.get(url)
            location = resp.headers.get("location", "N/A")
            print(f"\n{url}")
            print(f"  Status: {resp.status_code}")
            if resp.status_code in (301, 302, 303, 307, 308):
                print(f"  Redirect -> {location}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n\n" + "=" * 80)
    print("FOLLOWING REDIRECTS - AF_initDataCallback ANALYSIS")
    print("=" * 80)

    for url in URLS:
        try:
            resp = client_redirect.get(url)
            final_url = str(resp.url)

            # Count AF_initDataCallback
            af_pattern = r"AF_initDataCallback\s*\(\s*\{key:\s*'([^']+)',\s*(?:hash:\s*'[^']*',\s*)?(?:isError:\s*(?:true|false)\s*,\s*)?data:(.*?)\}\s*\)\s*;"
            af_blocks = re.findall(af_pattern, resp.text, re.DOTALL)

            keys = [k for k, _ in af_blocks]
            total_data = sum(len(d) for _, d in af_blocks)

            print(f"\n{url}")
            print(f"  Final URL: {final_url}")
            print(f"  Status: {resp.status_code}")
            print(f"  Body size: {len(resp.text)}")
            print(f"  AF keys: {keys}")
            print(f"  Total AF data: {total_data}")

            # Check if we got quote-specific data
            if "quote/" in url:
                # Look for BTC or AAPL specific data
                ticker = "BTC" if "BTC" in url else "AAPL" if "AAPL" in url else "GOOGL"
                has_ticker = ticker in resp.text
                print(f"  Contains '{ticker}' in response: {has_ticker}")

        except Exception as e:
            print(f"  ERROR: {e}")

    client_no_redirect.close()
    client_redirect.close()


if __name__ == "__main__":
    main()
