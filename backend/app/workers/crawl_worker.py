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
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
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

        try:
            pages_crawled = 0
            semaphore = asyncio.Semaphore(concurrency)
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

            # Producer-consumer pipeline queue
            extract_queue = asyncio.Queue(maxsize=concurrency * 2)
            extract_done = asyncio.Event()
            # Track content fingerprints to skip duplicate pages
            # (catches identical login walls / interstitials)
            _content_fingerprints: set[str] = set()

            # Strategy pinning: after first page succeeds, pin that strategy
            # for all remaining pages to skip the full tier cascade.
            _pinned_strategy: str | None = None
            _pinned_tier: int | None = None

            async def fetch_producer():
                """BFS loop: fetch pages, put raw results on extract_queue."""
                nonlocal pages_crawled, cancelled, _pinned_strategy, _pinned_tier

                empty_retries = 0
                max_empty_retries = 8  # Wait up to 8 times for consumer to add links

                while pages_crawled < request.max_pages and not cancelled:
                    batch_items = []
                    remaining = request.max_pages - pages_crawled
                    batch_size = min(concurrency * 2, remaining)

                    for _ in range(batch_size):
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
                        # links from the previous batch. Wait for queue to drain
                        # before giving up.
                        if not extract_queue.empty():
                            await extract_queue.join()
                            empty_retries = 0
                            continue  # Retry — consumer may have added new links
                        elif empty_retries < max_empty_retries:
                            empty_retries += 1
                            await asyncio.sleep(2)
                            continue  # Brief wait for consumer to finish
                        else:
                            break  # Truly no more URLs

                    empty_retries = 0

                    async def fetch_one(url: str, depth: int) -> dict | None:
                        nonlocal _pinned_strategy, _pinned_tier
                        async with semaphore:
                            try:
                                # Domain throttle
                                from urllib.parse import urlparse as _urlparse
                                from app.services.scraper import domain_throttle

                                _domain = _urlparse(url).netloc
                                if _domain:
                                    await domain_throttle(_domain, delay=0.2)

                                fetch_result = await asyncio.wait_for(
                                    crawler.fetch_page_only(
                                        url,
                                        pinned_strategy=_pinned_strategy,
                                        pinned_tier=_pinned_tier,
                                    ),
                                    timeout=120,
                                )
                                if fetch_result:
                                    # Pin strategy from first success
                                    if _pinned_strategy is None:
                                        ws = fetch_result.get("winning_strategy")
                                        wt = fetch_result.get("winning_tier")
                                        if ws and wt is not None:
                                            _pinned_strategy = ws
                                            _pinned_tier = wt
                                            logger.info(
                                                f"Pinned strategy: {ws} (tier {wt}) for crawl {job_id}"
                                            )
                                    return {
                                        "url": url,
                                        "depth": depth,
                                        "fetch_result": fetch_result,
                                    }
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

                extract_done.set()

            async def extract_consumer():
                """Extract content from fetched pages, save to DB."""
                nonlocal pages_crawled, cancelled

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

                            scrape_data = await loop.run_in_executor(
                                _extraction_executor,
                                extract_content,
                                fetch_result.get("raw_html", ""),
                                url,
                                req,
                                fetch_result.get("status_code", 0),
                                fetch_result.get("response_headers") or {},
                                fetch_result.get("screenshot_b64"),
                                fetch_result.get("action_screenshots", []),
                            )
                            discovered_links = scrape_data.links or []

                        # --- Content quality gate (signal-based, zero hardcoded strings) ---
                        # Uses structural extraction signals to detect pages
                        # with no real content.  Completely site-agnostic.
                        import re as _re

                        md_text = (scrape_data.markdown or "").strip()
                        _word_count = len(md_text.split())
                        _heading_count = len(scrape_data.headings or [])
                        _link_count = len(scrape_data.links or [])

                        # Signal 1: Content ratio — how much of the raw page
                        # survived main-content extraction?  Login walls and
                        # nav-only pages lose 90%+ when boilerplate is stripped.
                        _raw_html = ""
                        if "fetch_result" in item:
                            _raw_html = item["fetch_result"].get("raw_html", "")
                        elif scrape_data.html:
                            _raw_html = scrape_data.html
                        _raw_text_len = len(
                            _re.sub(r"<[^>]+>", " ", _raw_html).split()
                        ) if _raw_html else 0
                        _content_ratio = (
                            _word_count / _raw_text_len
                            if _raw_text_len > 100
                            else 1.0
                        )

                        # Signal 2: Link density — pages that are mostly links
                        # (nav pages, footer-only pages) have very high ratio.
                        _link_density = _link_count / max(_word_count, 1)

                        # Decision: skip only truly empty / broken pages.
                        # Previous thresholds were too aggressive and rejected
                        # most real pages (needed 800+ words with 2+ headings).
                        # Now we only skip pages with almost zero content.
                        _skip = False
                        if _word_count < 20:
                            _skip = True  # virtually empty page
                        elif _word_count < 50 and _content_ratio < 0.05:
                            _skip = True  # near-empty with almost no extraction

                        # Duplicate content detection — identical login walls,
                        # interstitials, etc. share the same text.  Hash the
                        # first 300 chars of markdown to detect near-dupes.
                        if not _skip and md_text:
                            _fp = md_text[:300]
                            if _fp in _content_fingerprints:
                                _skip = True
                                logger.info(
                                    f"Skipping duplicate content "
                                    f"({_word_count}w): {url}"
                                )
                            _content_fingerprints.add(_fp)

                        if _skip:
                            logger.info(
                                f"Skipping low-quality page "
                                f"({_word_count}w, {_heading_count}h, "
                                f"ratio={_content_ratio:.2f}, "
                                f"ld={_link_density:.2f}): {url}"
                            )
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

                        # Build rich metadata
                        metadata = {}
                        if scrape_data.metadata:
                            metadata = scrape_data.metadata.model_dump(
                                exclude_none=True
                            )
                        if scrape_data.structured_data:
                            metadata["structured_data"] = scrape_data.structured_data
                        if scrape_data.headings:
                            metadata["headings"] = scrape_data.headings
                        if scrape_data.images:
                            metadata["images"] = scrape_data.images
                        if scrape_data.links_detail:
                            metadata["links_detail"] = scrape_data.links_detail

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

                        # Capture screenshot — only for pages that pass
                        # the quality gate to avoid wasting browser time.
                        # Retry once if the browser was mid-reinitialisation.
                        screenshot_val = scrape_data.screenshot
                        if not screenshot_val:
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
                                                    type="jpeg",
                                                    quality=80,
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

                        # Store result
                        async with session_factory() as db:
                            job_result = JobResult(
                                job_id=UUID(job_id),
                                url=url,
                                markdown=scrape_data.markdown,
                                html=scrape_data.html,
                                links=scrape_data.links if scrape_data.links else None,
                                extract=extract_data,
                                metadata_=metadata if metadata else None,
                                screenshot_url=screenshot_val,
                            )
                            db.add(job_result)

                            pages_crawled += 1

                            job = await db.get(Job, UUID(job_id))
                            if job:
                                job.completed_pages = pages_crawled
                                if job.status == "cancelled":
                                    cancelled = True
                            await db.commit()

                        # Add discovered links to frontier
                        if discovered_links:
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

            # Mark job as completed
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job and job.status != "cancelled":
                    job.status = "completed"
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
                                    "event": "job.completed"
                                    if job.status == "completed"
                                    else "job.cancelled",
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
