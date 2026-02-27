"""
Google Finance reverse engineering - Step 1: Fetch and analyze raw HTML responses.
"""
import httpx
import re
import json
import sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

URLS = {
    "market_overview": "https://www.google.com/finance/beta?hl=en",
    "quote_btc": "https://www.google.com/finance/beta/quote/BTC-USD?hl=en",
    "quote_aapl": "https://www.google.com/finance/beta/quote/AAPL:NASDAQ?hl=en",
}


def analyze_response(name: str, html: str):
    print(f"\n{'='*80}")
    print(f"ANALYZING: {name}")
    print(f"{'='*80}")
    print(f"Response length: {len(html)} bytes")

    # Check for AF_initDataCallback
    af_matches = re.findall(r'AF_initDataCallback\s*\(\s*\{', html)
    print(f"\nAF_initDataCallback occurrences: {len(af_matches)}")

    # Extract all AF_initDataCallback blocks with their keys
    af_pattern = r"AF_initDataCallback\s*\(\s*\{key:\s*'([^']+)',\s*(?:hash:\s*'[^']*',\s*)?(?:isError:\s*(?:true|false)\s*,\s*)?data:(.*?)\}\s*\)\s*;"
    af_blocks = re.findall(af_pattern, html, re.DOTALL)
    print(f"AF_initDataCallback blocks with keys: {len(af_blocks)}")

    for key, data_str in af_blocks:
        data_preview = data_str.strip()[:200]
        print(f"\n  Key: {key}")
        print(f"  Data preview: {data_preview}...")
        print(f"  Data length: {len(data_str.strip())}")

    # Check for other data patterns
    # Session-prefixed JSON (like Google Images)
    session_json = re.findall(r'\)\]\}\'[\s]*\n', html)
    print(f"\nSession-prefixed JSON patterns: {len(session_json)}")

    # window.__data or similar
    window_data = re.findall(r'window\.__?(\w+)\s*=', html)
    if window_data:
        print(f"window.__X patterns: {window_data[:10]}")

    # data-ved, data-atid patterns (Google's tracking)
    data_attrs = set(re.findall(r'data-([a-z-]+)=', html))
    if data_attrs:
        print(f"data-* attributes: {sorted(list(data_attrs))[:20]}")

    # Check for <script> tags with type="application/json"
    json_scripts = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"\n<script type='application/json'> blocks: {len(json_scripts)}")

    # Check for __NEXT_DATA__ (Next.js)
    next_data = re.findall(r'__NEXT_DATA__', html)
    print(f"__NEXT_DATA__: {len(next_data)}")

    # Check for any batch execute references
    batch_refs = re.findall(r'_/data/[^\'"]+', html)
    if batch_refs:
        print(f"\nBatch execute refs: {batch_refs[:5]}")

    # Save raw HTML for further analysis
    safe_name = name.replace(" ", "_")
    with open(f"/home/lostboi/aefoa/web-crawler/backend/gfinance_{safe_name}.html", "w") as f:
        f.write(html)
    print(f"\nSaved to gfinance_{safe_name}.html")


def main():
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30)

    for name, url in URLS.items():
        try:
            resp = client.get(url)
            print(f"\n[{name}] Status: {resp.status_code}, URL: {resp.url}")
            analyze_response(name, resp.text)
        except Exception as e:
            print(f"\n[{name}] ERROR: {e}")

    client.close()


if __name__ == "__main__":
    main()
