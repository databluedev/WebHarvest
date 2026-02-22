import asyncio
import base64
import logging
import time as _time_mod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_WORKER_NAME = "crawl"

# Shared thread pool for CPU-bound content extraction in crawl pipeline
_extraction_executor = ThreadPoolExecutor(max_workers=8)


def _run_async(coro):
    # Drop stale pool references from a previous task whose loop is dead.
    # cleanup_async_pools() in the finally block can be skipped if Celery
    # kills the task (time limit), leaving refs to a closed loop.
    from app.services.scraper import reset_pool_state_sync
    reset_pool_state_sync()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Tear down all pooled async clients BEFORE closing the loop
        # so nothing is left referencing a dead event loop.
        try:
            from app.services.scraper import cleanup_async_pools
            loop.run_until_complete(cleanup_async_pools())
        except Exception:
            pass
        loop.close()


@celery_app.task(
    name="app.workers.crawl_worker.process_crawl",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=3600,
    time_limit=3660,
)
def process_crawl(self, job_id: str, config: dict):
    """Process a crawl job using BFS crawler with producer-consumer pipeline."""
    from app.core.metrics import worker_task_total, worker_task_duration_seconds, worker_active_tasks

    _start = _time_mod.monotonic()
    worker_active_tasks.labels(worker=_WORKER_NAME).inc()

    async def _do_crawl():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.crawl import CrawlRequest
        from app.services.crawler import WebCrawler
        from app.services.dedup import normalize_url
        from app.services.llm_extract import extract_with_llm
        from app.services.scraper import extract_content

        # Create fresh DB connections for this event loop
        session_factory, db_engine = create_worker_session_factory()

        request = CrawlRequest(**config)
        concurrency = max(1, min(request.concurrency, 10))

        # Load proxy manager if use_proxy is set
        proxy_manager = None
        if request.use_proxy:
            from app.services.proxy import ProxyManager

            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    proxy_manager = await ProxyManager.from_user(db, job.user_id)

        crawler = WebCrawler(job_id, request, proxy_manager=proxy_manager)
        await crawler.initialize()

        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                return
            user_id = job.user_id
            job.status = "running"
            job.total_pages = request.max_pages
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        # Determine extract config from scrape_options
        extract_config = None
        if request.scrape_options and request.scrape_options.extract:
            extract_config = request.scrape_options.extract

        # User's originally requested formats — used to decide what to store
        # (the crawler internally forces "links" for BFS, but we don't store
        # them in DB unless the user actually asked for "links").
        _user_formats = set()
        if request.scrape_options:
            _user_formats = set(request.scrape_options.formats)

        try:
            pages_crawled = 0
            # Memory-adaptive semaphore: adjusts concurrency based on system memory
            from app.services.memory_adaptive import MemoryAdaptiveSemaphore
            semaphore = MemoryAdaptiveSemaphore(
                base_limit=concurrency,
                min_limit=1,
                max_limit=concurrency * 2,
            )
            await semaphore.start_monitoring()
            cancelled = False
            loop = asyncio.get_running_loop()

            # Suppress Playwright TargetClosedError from cancelled race futures.
            # During concurrent crawls, race cancellation closes browser pages
            # while Playwright operations are still in-flight, producing
            # "Future exception was never retrieved" errors that can kill the loop.
            _original_handler = loop.get_exception_handler()

            def _crawl_exception_handler(loop_ref, context):
                exc = context.get("exception")
                if exc:
                    exc_name = type(exc).__name__
                    exc_msg = str(exc).lower()
                    if (
                        "TargetClosedError" in exc_name
                        or "target" in exc_name.lower()
                        or "closed" in exc_msg
                        or "event loop is closed" in exc_msg
                    ):
                        logger.debug(f"Suppressed browser error in crawl loop: {exc_name}")
                        return
                if _original_handler:
                    _original_handler(loop_ref, context)
                else:
                    loop_ref.default_exception_handler(context)

            loop.set_exception_handler(_crawl_exception_handler)

            # =============================================================
            # Session warm-up: establish cookies before BFS.
            # Hard sites (Amazon, etc.) reject requests probabilistically.
            # Retry the seed URL with the full scrape pipeline (all tiers
            # including advanced_prewarm) until we get a valid response,
            # then transfer cookies into crawl_session for fast subsequent
            # fetches. The successful result is used as page 1 directly.
            # =============================================================
            _warmup_result = None
            _warmup_max = 3
            for _warmup_attempt in range(_warmup_max):
                try:
                    logger.warning(
                        f"Session warm-up {_warmup_attempt + 1}/{_warmup_max} "
                        f"for {request.url}"
                    )
                    _warmup_scrape = await asyncio.wait_for(
                        crawler.scrape_page(request.url),
                        timeout=120,
                    )
                    _warmup_data = _warmup_scrape["scrape_data"]
                    _warmup_md = (_warmup_data.markdown or "").strip()
                    _warmup_words = len(_warmup_md.split())
                    _warmup_html = _warmup_data.html or ""

                    # Validate: reject blocked / garbage pages that
                    # scrape_url returns as "best available" fallback.
                    from app.services.scraper import _looks_blocked
                    _wu_blocked = _looks_blocked(_warmup_html)
                    if _wu_blocked:
                        logger.warning(
                            f"Session warm-up attempt {_warmup_attempt + 1} "
                            f"returned blocked content ({_warmup_words} words, "
                            f"{len(_warmup_html)} chars HTML)"
                        )
                    elif _warmup_words < 50:
                        logger.warning(
                            f"Session warm-up attempt {_warmup_attempt + 1} got "
                            f"thin content ({_warmup_words} words)"
                        )
                    else:
                        logger.warning(
                            f"Session warm-up succeeded ({_warmup_words} words) "
                            f"on attempt {_warmup_attempt + 1}"
                        )
                        _warmup_result = _warmup_scrape
                        break
                except Exception as e:
                    logger.warning(
                        f"Session warm-up attempt {_warmup_attempt + 1} failed: {e}"
                    )

                if _warmup_attempt < _warmup_max - 1:
                    _backoff = (2 ** _warmup_attempt) * 5  # 5s, 10s
                    logger.warning(f"Warm-up backoff: {_backoff}s")
                    await asyncio.sleep(_backoff)

            # Pinned strategy — set by warm-up or by first successful fetch
            _pinned_strategy: str | None = None
            _pinned_tier: int | None = None

            # If warm-up succeeded, save result as page 1 and mark seed visited
            _warmup_links = []
            if _warmup_result:
                _wu_data = _warmup_result["scrape_data"]
                _warmup_links = _warmup_result.get("discovered_links", [])

                # Build metadata for DB storage
                _wu_meta = {}
                if _wu_data.metadata:
                    _wu_meta = _wu_data.metadata.model_dump(exclude_none=True)
                if _wu_data.structured_data and (not _user_formats or "structured_data" in _user_formats):
                    _wu_meta["structured_data"] = _wu_data.structured_data
                if _wu_data.headings and (not _user_formats or "headings" in _user_formats):
                    _wu_meta["headings"] = _wu_data.headings
                if _wu_data.images and (not _user_formats or "images" in _user_formats):
                    _wu_meta["images"] = _wu_data.images
                if _wu_data.links_detail and (not _user_formats or "links" in _user_formats):
                    _wu_meta["links_detail"] = _wu_data.links_detail
                if _wu_data.product_data:
                    _wu_meta["product_data"] = _wu_data.product_data
                if _wu_data.tables and (not _user_formats or "tables" in _user_formats):
                    _wu_meta["tables"] = _wu_data.tables
                if _wu_data.content_hash:
                    _wu_meta["content_hash"] = _wu_data.content_hash

                async with session_factory() as db:
                    job_result = JobResult(
                        job_id=UUID(job_id),
                        url=request.url,
                        markdown=_wu_data.markdown if not _user_formats or "markdown" in _user_formats else None,
                        html=_wu_data.html if not _user_formats or "html" in _user_formats else None,
                        links=_wu_data.links if _wu_data.links and (not _user_formats or "links" in _user_formats) else None,
                        metadata_=_wu_meta if _wu_meta else None,
                        screenshot_url=_wu_data.screenshot if not _user_formats or "screenshot" in _user_formats else None,
                    )
                    db.add(job_result)

                    pages_crawled = 1
                    _wu_wc = len((_wu_data.markdown or "").split())
                    logger.warning(
                        f"Saved page {pages_crawled}/{request.max_pages}: "
                        f"{request.url} ({_wu_wc}w) [warm-up]"
                    )

                    job = await db.get(Job, UUID(job_id))
                    if job:
                        job.completed_pages = pages_crawled
                    await db.commit()

                # Mark seed URL as visited so BFS doesn't re-fetch it
                seed_norm = normalize_url(request.url)
                await crawler.mark_visited(seed_norm)

                # Seed frontier with discovered links for BFS continuation
                if _warmup_links and pages_crawled < request.max_pages:
                    await crawler.add_to_frontier(_warmup_links, 1)

                # Pin strategy to crawl_session — cookies are now established
                _pinned_strategy = "crawl_session"
                _pinned_tier = 2
                logger.warning(
                    f"Pinned strategy: crawl_session (from warm-up) "
                    f"for crawl {job_id}"
                )

            # Producer-consumer pipeline queue
            extract_queue = asyncio.Queue(maxsize=concurrency * 2)
            extract_done = asyncio.Event()

            async def fetch_producer():
                """BFS loop: fetch pages, put raw results on extract_queue."""
                nonlocal pages_crawled, cancelled, _pinned_strategy, _pinned_tier

                empty_retries = 0
                max_empty_retries = 5  # Wait up to 5 times for consumer to add links

                while pages_crawled < request.max_pages and not cancelled:
                    batch_items = []
                    remaining = request.max_pages - pages_crawled
                    # Fetch extra to compensate for pages that may be
                    # skipped (duplicates, empty, failures).
                    batch_size = min(concurrency * 2, remaining + concurrency)

                    while len(batch_items) < batch_size:
                        next_item = await crawler.get_next_url()
                        if not next_item:
                            break
                        url, depth = next_item

                        norm_url = normalize_url(url)
                        if await crawler.is_visited(norm_url):
                            continue

                        await crawler.mark_visited(norm_url)
                        batch_items.append((url, depth))

                    if not batch_items:
                        # Frontier is empty — but consumer may still be extracting
                        # links from the previous batch.
                        #
                        # IMPORTANT: Queue.empty() only checks for items waiting
                        # to be gotten. Items already taken by the consumer but
                        # still being processed (task_done() not yet called) are
                        # NOT detected. join() properly waits for ALL unfinished
                        # items, and returns instantly if nothing is pending.
                        try:
                            await asyncio.wait_for(
                                extract_queue.join(), timeout=60
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Extract queue drain timed out for {job_id}"
                            )

                        if empty_retries < max_empty_retries:
                            empty_retries += 1
                            await asyncio.sleep(1)
                            continue  # Retry — consumer may have added new links
                        else:
                            break  # Truly no more URLs

                    empty_retries = 0

                    async def fetch_one(url: str, depth: int) -> dict | None:
                        nonlocal _pinned_strategy, _pinned_tier
                        async with semaphore:
                            try:
                                # Domain throttle — respect robots.txt Crawl-Delay
                                from urllib.parse import urlparse as _urlparse
                                from app.services.scraper import domain_throttle

                                _domain = _urlparse(url).netloc
                                if _domain:
                                    _crawl_delay = crawler.get_crawl_delay(url)
                                    _delay = max(0.1, _crawl_delay or 0.0)
                                    await domain_throttle(_domain, delay=_delay)

                                fetch_result = await asyncio.wait_for(
                                    crawler.fetch_page_only(
                                        url,
                                        pinned_strategy=_pinned_strategy,
                                        pinned_tier=_pinned_tier,
                                    ),
                                    timeout=120,
                                )
                                if fetch_result:
                                    html_len = len(fetch_result.get("raw_html", ""))
                                    ws = fetch_result.get("winning_strategy", "?")
                                    sc = fetch_result.get("status_code", 0)
                                    logger.warning(
                                        f"Fetched {url} via {ws} ({html_len} chars, {sc})"
                                    )

                                    # Firecrawl-style escalation: if the page
                                    # returned a block status (401/403/429) or
                                    # looks blocked, unpin the strategy so the
                                    # next page retries all strategies fresh.
                                    _is_blocked = sc in (401, 403, 429)
                                    if not _is_blocked:
                                        from app.services.scraper import _looks_blocked
                                        raw = fetch_result.get("raw_html", "")
                                        _is_blocked = _looks_blocked(raw)

                                    if _is_blocked and _pinned_strategy is not None:
                                        logger.warning(
                                            f"Strategy escalation: {ws} returned "
                                            f"blocked ({sc}) for {url}, unpinning"
                                        )
                                        _pinned_strategy = None
                                        _pinned_tier = None

                                    # Don't queue blocked pages for extraction —
                                    # they contain bot-detection garbage, not content.
                                    if _is_blocked:
                                        logger.warning(f"Skipping blocked page: {url}")
                                        return None

                                    # Pin strategy from first success
                                    if _pinned_strategy is None:
                                        wt = fetch_result.get("winning_tier")
                                        if ws and wt is not None:
                                            if ws in ("advanced_prewarm", "google_search_chain"):
                                                _pinned_strategy = "crawl_session"
                                                _pinned_tier = 2
                                                logger.warning(
                                                    f"Pinned strategy: crawl_session (cookies from {ws}) for crawl {job_id}"
                                                )
                                            else:
                                                _pinned_strategy = ws
                                                _pinned_tier = wt
                                                logger.warning(
                                                    f"Pinned strategy: {ws} (tier {wt}) for crawl {job_id}"
                                                )
                                    return {
                                        "url": url,
                                        "depth": depth,
                                        "fetch_result": fetch_result,
                                    }
                                logger.warning(f"fetch_page_only returned None for {url}, trying scrape_page")
                                # Fallback to full scrape — shorter timeout since
                                # the fast path already spent time trying.
                                result = await asyncio.wait_for(
                                    crawler.scrape_page(url),
                                    timeout=60,
                                )
                                return {
                                    "url": url,
                                    "depth": depth,
                                    "scrape_data": result["scrape_data"],
                                    "discovered_links": result["discovered_links"],
                                }
                            except asyncio.TimeoutError:
                                logger.warning(f"Fetch timed out for {url} after 120s")
                                return None
                            except Exception as e:
                                logger.warning(f"Failed to fetch {url}: {e}")
                                return None

                    tasks = [fetch_one(url, depth) for url, depth in batch_items]
                    results = await asyncio.gather(*tasks)

                    for result in results:
                        if result is None:
                            continue
                        if pages_crawled >= request.max_pages or cancelled:
                            break
                        await extract_queue.put(result)

                logger.warning(
                    f"Producer done for {job_id}: pages_crawled={pages_crawled}, "
                    f"cancelled={cancelled}"
                )
                extract_done.set()

            async def extract_consumer():
                """Extract content from fetched pages, save to DB."""
                nonlocal pages_crawled, cancelled, _pinned_strategy, _pinned_tier

                while True:
                    try:
                        item = await asyncio.wait_for(extract_queue.get(), timeout=5)
                    except asyncio.TimeoutError:
                        if extract_done.is_set() and extract_queue.empty():
                            break
                        continue

                    try:
                        url = item["url"]
                        depth = item["depth"]

                        if "scrape_data" in item:
                            # Already fully extracted (fallback path)
                            scrape_data = item["scrape_data"]
                            discovered_links = item.get("discovered_links", [])
                        else:
                            # Pipeline path: extract content in thread pool
                            fetch_result = item["fetch_result"]
                            req = fetch_result["request"]

                            scrape_data = await asyncio.wait_for(
                                loop.run_in_executor(
                                    _extraction_executor,
                                    extract_content,
                                    fetch_result.get("raw_html", ""),
                                    url,
                                    req,
                                    fetch_result.get("status_code", 0),
                                    fetch_result.get("response_headers") or {},
                                    fetch_result.get("screenshot_b64"),
                                    fetch_result.get("action_screenshots", []),
                                ),
                                timeout=60,  # Per-page extraction timeout
                            )
                            discovered_links = scrape_data.links or []

                        # Skip truly empty pages — catches bot-detection
                        # interstitials and blank renders, but preserves thin
                        # landing pages, category indexes, and short content.
                        md_text = (scrape_data.markdown or "").strip()
                        _word_count = len(md_text.split())
                        _skip = False

                        if _word_count < 15:
                            _skip = True
                            logger.warning(f"Skipping thin page ({_word_count} words): {url}")

                        # Seed URL retry: if the very first page is thin
                        # (e.g. Amazon session-gate stub), retry once —
                        # cookies are now set from the first attempt.
                        if _skip and pages_crawled == 0 and depth == 0:
                            logger.info(f"Seed URL thin ({_word_count} words), retrying once: {url}")
                            try:
                                _retry_result = await asyncio.wait_for(
                                    crawler.scrape_page(url),
                                    timeout=60,
                                )
                                scrape_data = _retry_result["scrape_data"]
                                discovered_links = _retry_result.get("discovered_links", [])
                                md_text = (scrape_data.markdown or "").strip()
                                _word_count = len(md_text.split())
                                _skip = _word_count < 15
                                if not _skip:
                                    logger.info(f"Seed URL retry succeeded ({_word_count} words): {url}")
                            except Exception as _retry_err:
                                logger.warning(f"Seed URL retry failed for {url}: {_retry_err}")

                        if _skip:
                            # Still harvest links for frontier expansion
                            if discovered_links:
                                await crawler.add_to_frontier(
                                    discovered_links, depth + 1
                                )
                            # task_done() is called in the finally block
                            continue

                        # Enforce page limit — producer may have queued
                        # extra items before the counter caught up.
                        if pages_crawled >= request.max_pages:
                            if discovered_links:
                                await crawler.add_to_frontier(
                                    discovered_links, depth + 1
                                )
                            continue

                        # Build rich metadata — only include data the user requested
                        metadata = {}
                        if scrape_data.metadata:
                            metadata = scrape_data.metadata.model_dump(
                                exclude_none=True
                            )
                        if scrape_data.structured_data and (not _user_formats or "structured_data" in _user_formats):
                            metadata["structured_data"] = scrape_data.structured_data
                        if scrape_data.headings and (not _user_formats or "headings" in _user_formats):
                            metadata["headings"] = scrape_data.headings
                        if scrape_data.images and (not _user_formats or "images" in _user_formats):
                            metadata["images"] = scrape_data.images
                        if scrape_data.links_detail and (not _user_formats or "links" in _user_formats):
                            metadata["links_detail"] = scrape_data.links_detail
                        if scrape_data.product_data:
                            metadata["product_data"] = scrape_data.product_data
                        if scrape_data.tables and (not _user_formats or "tables" in _user_formats):
                            metadata["tables"] = scrape_data.tables
                        if scrape_data.selector_data:
                            metadata["selector_data"] = scrape_data.selector_data
                        if scrape_data.fit_markdown:
                            metadata["fit_markdown"] = scrape_data.fit_markdown
                        if scrape_data.citations:
                            metadata["citations"] = scrape_data.citations
                        if scrape_data.markdown_with_citations:
                            metadata["markdown_with_citations"] = scrape_data.markdown_with_citations
                        if scrape_data.content_hash:
                            metadata["content_hash"] = scrape_data.content_hash

                        # LLM extraction if configured
                        extract_data = None
                        if extract_config and scrape_data.markdown:
                            try:
                                async with session_factory() as llm_db:
                                    extract_data = await asyncio.wait_for(
                                        extract_with_llm(
                                            db=llm_db,
                                            user_id=user_id,
                                            content=scrape_data.markdown,
                                            prompt=extract_config.prompt,
                                            schema=extract_config.schema_,
                                        ),
                                        timeout=90,
                                    )
                            except Exception as e:
                                logger.warning(f"LLM extraction failed for {url}: {e}")

                        # Capture screenshot — only if user requested it.
                        # Retry once if the browser was mid-reinitialisation.
                        screenshot_val = None
                        if _user_formats and "screenshot" not in _user_formats:
                            pass  # User didn't request screenshots — skip entirely
                        elif not (screenshot_val := scrape_data.screenshot):
                            _raw_for_ss = ""
                            if "fetch_result" in item:
                                _raw_for_ss = item["fetch_result"].get(
                                    "raw_html", ""
                                )
                            elif scrape_data.html:
                                _raw_for_ss = scrape_data.html
                            if _raw_for_ss:
                                for _ss_attempt in range(2):
                                    # Try crawl session first
                                    screenshot_val = (
                                        await crawler.take_screenshot(
                                            url, _raw_for_ss
                                        )
                                    )
                                    if screenshot_val:
                                        break
                                    # Fallback: browser_pool (independent
                                    # browser instance)
                                    try:
                                        from app.services.browser import (
                                            browser_pool,
                                        )

                                        async with browser_pool.get_page(
                                            target_url=url
                                        ) as _ss_page:
                                            await _ss_page.set_content(
                                                _raw_for_ss,
                                                wait_until=(
                                                    "domcontentloaded"
                                                ),
                                            )
                                            await _ss_page.wait_for_timeout(
                                                500
                                            )
                                            _ss_bytes = (
                                                await _ss_page.screenshot(
                                                    type="png",
                                                    full_page=True,
                                                )
                                            )
                                            screenshot_val = (
                                                base64.b64encode(
                                                    _ss_bytes
                                                ).decode()
                                            )
                                    except Exception:
                                        pass
                                    if screenshot_val:
                                        break
                                    # Brief wait for browser to reinitialize
                                    if _ss_attempt == 0:
                                        await asyncio.sleep(2)

                        # Store result — only include fields the user requested
                        async with session_factory() as db:
                            job_result = JobResult(
                                job_id=UUID(job_id),
                                url=url,
                                markdown=scrape_data.markdown if not _user_formats or "markdown" in _user_formats else None,
                                html=scrape_data.html if not _user_formats or "html" in _user_formats else None,
                                links=scrape_data.links if scrape_data.links and (not _user_formats or "links" in _user_formats) else None,
                                extract=extract_data,
                                metadata_=metadata if metadata else None,
                                screenshot_url=screenshot_val if not _user_formats or "screenshot" in _user_formats else None,
                            )
                            db.add(job_result)

                            pages_crawled += 1
                            logger.warning(
                                f"Saved page {pages_crawled}/{request.max_pages}: {url} "
                                f"({_word_count}w)"
                            )

                            job = await db.get(Job, UUID(job_id))
                            if job:
                                job.completed_pages = pages_crawled
                                if job.status == "cancelled":
                                    cancelled = True
                            await db.commit()

                        # Add discovered links to frontier (skip if we've
                        # already hit the page limit — no point expanding)
                        if discovered_links and pages_crawled < request.max_pages:
                            await crawler.add_to_frontier(discovered_links, depth + 1)

                    except Exception as e:
                        logger.warning(
                            f"Extract/save failed for {item.get('url', '?')}: {e}"
                        )
                    finally:
                        extract_queue.task_done()

            # Run producer and consumer concurrently
            await asyncio.gather(
                fetch_producer(),
                extract_consumer(),
            )

            # Mark job as completed or failed
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job and job.status != "cancelled":
                    if pages_crawled > 0:
                        job.status = "completed"
                    else:
                        job.status = "failed"
                        job.error = "Crawl finished but no pages were successfully scraped. The site may be blocking requests."
                    job.total_pages = pages_crawled
                    job.completed_pages = pages_crawled
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            # Send webhook if configured
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook

                    async with session_factory() as db:
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            await send_webhook(
                                url=request.webhook_url,
                                payload={
                                    "event": f"job.{job.status}",
                                    "job_id": job_id,
                                    "job_type": "crawl",
                                    "status": job.status,
                                    "total_pages": job.total_pages,
                                    "completed_pages": job.completed_pages,
                                    "created_at": job.created_at.isoformat()
                                    if job.created_at
                                    else None,
                                    "completed_at": job.completed_at.isoformat()
                                    if job.completed_at
                                    else None,
                                },
                                secret=request.webhook_secret,
                            )
                except Exception as e:
                    logger.warning(f"Webhook delivery failed for crawl {job_id}: {e}")

        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()

            # Send failure webhook
            if request.webhook_url:
                try:
                    from app.services.webhook import send_webhook

                    await send_webhook(
                        url=request.webhook_url,
                        payload={
                            "event": "job.failed",
                            "job_id": job_id,
                            "job_type": "crawl",
                            "status": "failed",
                            "error": str(e),
                        },
                        secret=request.webhook_secret,
                    )
                except Exception:
                    pass
        finally:
            # Stop memory monitoring
            try:
                await semaphore.stop_monitoring()
            except Exception:
                pass
            # Restore original exception handler
            try:
                loop.set_exception_handler(_original_handler)
            except Exception:
                pass
            await crawler.cleanup()
            await db_engine.dispose()

    try:
        _run_async(_do_crawl())
        worker_task_total.labels(worker=_WORKER_NAME, status="success").inc()
    except Exception:
        worker_task_total.labels(worker=_WORKER_NAME, status="failure").inc()
        raise
    finally:
        worker_active_tasks.labels(worker=_WORKER_NAME).dec()
        worker_task_duration_seconds.labels(worker=_WORKER_NAME).observe(
            _time_mod.monotonic() - _start
        )
