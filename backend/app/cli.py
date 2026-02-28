"""CLI tool for DataBlue — command-line crawling and scraping.

Usage:
    python -m app.cli scrape https://example.com
    python -m app.cli scrape https://example.com --formats markdown html links
    python -m app.cli scrape https://example.com --css "h1.title"
    python -m app.cli scrape https://example.com --xpath "//div[@class='price']/text()"
    python -m app.cli crawl https://example.com --max-pages 50 --max-depth 2
    python -m app.cli crawl https://example.com --strategy dfs
    python -m app.cli map https://example.com
"""

import argparse
import asyncio
import json
import logging
import sys


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


async def _cmd_scrape(args):
    """Scrape a single URL."""
    from app.schemas.scrape import ScrapeRequest
    from app.services.scraper import scrape_url

    formats = args.formats or ["markdown"]
    request = ScrapeRequest(
        url=args.url,
        formats=formats,
        only_main_content=args.main_content,
        timeout=args.timeout * 1000,
        css_selector=args.css,
        xpath=args.xpath,
    )

    result = await scrape_url(request)

    output = {}
    if result.markdown:
        output["markdown"] = result.markdown
    if result.html:
        output["html"] = result.html
    if result.links:
        output["links"] = result.links
    if result.structured_data:
        output["structured_data"] = result.structured_data
    if result.product_data:
        output["product_data"] = result.product_data
    if result.tables:
        output["tables"] = result.tables
    if result.selector_data:
        output["selector_data"] = result.selector_data
    if result.fit_markdown:
        output["fit_markdown"] = result.fit_markdown
    if result.citations:
        output["citations"] = result.citations
    if result.metadata:
        output["metadata"] = result.metadata.model_dump(exclude_none=True)

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.output == "markdown" and output.get("markdown"):
        print(output["markdown"])
    elif args.output == "text":
        for key, value in output.items():
            if isinstance(value, str):
                print(f"--- {key} ---")
                print(value[:2000])
                print()
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


async def _cmd_crawl(args):
    """Crawl a site starting from a URL."""
    from app.schemas.crawl import CrawlRequest, ScrapeOptions
    from app.services.crawler import WebCrawler
    from app.services.dedup import normalize_url
    from app.services.scraper import extract_content

    config = CrawlRequest(
        url=args.url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        crawl_strategy=args.strategy,
        allow_external_links=args.external,
        scrape_options=ScrapeOptions(formats=args.formats or ["markdown"]),
    )

    crawler = WebCrawler("cli-crawl", config)

    # Simplified crawl without browser session for CLI
    # Just use the strategy and HTTP-based scraping
    from app.services.deep_crawl.strategies import BFSStrategy, DFSStrategy, BestFirstStrategy

    strategy_kwargs = {
        "max_depth": config.max_depth,
        "max_pages": config.max_pages,
        "include_external": config.allow_external_links,
    }

    if args.strategy == "dfs":
        strategy = DFSStrategy(**strategy_kwargs)
    elif args.strategy == "bff":
        strategy = BestFirstStrategy(**strategy_kwargs)
    else:
        strategy = BFSStrategy(**strategy_kwargs)

    strategy.seed(args.url)
    pages_crawled = 0
    results = []

    while pages_crawled < args.max_pages:
        batch = await strategy.get_next_urls()
        if not batch:
            break

        for item in batch:
            if pages_crawled >= args.max_pages:
                break
            url = item.url
            if url in strategy._state.visited:
                continue

            strategy._state.visited.add(url)

            try:
                from app.schemas.scrape import ScrapeRequest
                from app.services.scraper import scrape_url

                request = ScrapeRequest(
                    url=url,
                    formats=args.formats or ["markdown", "links"],
                    only_main_content=True,
                    timeout=30000,
                )
                result = await scrape_url(request)
                pages_crawled += 1
                strategy._state.pages_crawled = pages_crawled

                page_data = {"url": url, "depth": item.depth}
                if result.markdown:
                    page_data["markdown"] = result.markdown[:500] + "..." if len(result.markdown or "") > 500 else result.markdown
                if result.metadata:
                    page_data["title"] = result.metadata.title

                results.append(page_data)
                print(
                    f"[{pages_crawled}/{args.max_pages}] {url} "
                    f"({len(result.markdown or '')} chars)",
                    file=sys.stderr,
                )

                # Add discovered links
                if result.links:
                    await strategy.add_discovered_urls(
                        result.links, url, item.depth + 1
                    )

            except Exception as e:
                print(f"[ERROR] {url}: {e}", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for page in results:
            print(f"\n{'='*60}")
            print(f"URL: {page['url']} (depth: {page.get('depth', 0)})")
            if page.get("title"):
                print(f"Title: {page['title']}")
            if page.get("markdown"):
                print(page["markdown"])

    print(f"\nCrawled {pages_crawled} pages", file=sys.stderr)


async def _cmd_map(args):
    """Map a site's structure via sitemap + link discovery."""
    from app.services.mapper import _parse_sitemaps

    print(f"Mapping {args.url}...", file=sys.stderr)
    links = await _parse_sitemaps(args.url)

    urls = []
    for link in (links or []):
        urls.append({
            "url": link.url,
            "lastmod": link.lastmod,
            "priority": link.priority,
        })

    if args.output == "json":
        print(json.dumps(urls, indent=2, ensure_ascii=False, default=str))
    else:
        for u in urls:
            print(u["url"])

    print(f"\nFound {len(urls)} URLs in sitemap", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="datablue",
        description="DataBlue CLI — crawl, scrape, and map websites",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-o", "--output", default="json",
        choices=["json", "markdown", "text"],
        help="Output format (default: json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- scrape ---
    scrape_parser = subparsers.add_parser("scrape", help="Scrape a single URL")
    scrape_parser.add_argument("url", help="URL to scrape")
    scrape_parser.add_argument(
        "--formats", nargs="+", default=None,
        help="Output formats: markdown, html, links, structured_data, tables, headings, images",
    )
    scrape_parser.add_argument("--main-content", action="store_true", help="Extract main content only")
    scrape_parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    scrape_parser.add_argument("--css", default=None, help="CSS selector for targeted extraction")
    scrape_parser.add_argument("--xpath", default=None, help="XPath expression for extraction")

    # --- crawl ---
    crawl_parser = subparsers.add_parser("crawl", help="Crawl a website")
    crawl_parser.add_argument("url", help="Starting URL")
    crawl_parser.add_argument("--max-pages", type=int, default=10, help="Max pages to crawl")
    crawl_parser.add_argument("--max-depth", type=int, default=3, help="Max crawl depth")
    crawl_parser.add_argument(
        "--strategy", default="bfs", choices=["bfs", "dfs", "bff"],
        help="Crawl strategy: bfs, dfs, or bff (best-first)",
    )
    crawl_parser.add_argument("--external", action="store_true", help="Allow external links")
    crawl_parser.add_argument(
        "--formats", nargs="+", default=None,
        help="Output formats for each page",
    )

    # --- map ---
    map_parser = subparsers.add_parser("map", help="Map site structure via sitemap")
    map_parser.add_argument("url", help="Site URL to map")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    _setup_logging(args.verbose)

    if args.command == "scrape":
        asyncio.run(_cmd_scrape(args))
    elif args.command == "crawl":
        asyncio.run(_cmd_crawl(args))
    elif args.command == "map":
        asyncio.run(_cmd_map(args))


if __name__ == "__main__":
    main()
