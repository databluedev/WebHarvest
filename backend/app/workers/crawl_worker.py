import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.crawl_worker.process_crawl", bind=True, max_retries=1)
def process_crawl(self, job_id: str, config: dict):
    """Process a crawl job using BFS crawler."""

    async def _do_crawl():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.crawl import CrawlRequest
        from app.services.crawler import WebCrawler

        # Create fresh DB connections for this event loop
        session_factory, db_engine = create_worker_session_factory()

        request = CrawlRequest(**config)

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
            job.status = "running"
            job.total_pages = request.max_pages  # Set upper bound for progress tracking
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            pages_crawled = 0

            while pages_crawled < request.max_pages:
                next_item = await crawler.get_next_url()
                if not next_item:
                    break

                url, depth = next_item

                if await crawler.is_visited(url):
                    continue

                await crawler.mark_visited(url)

                try:
                    result = await crawler.scrape_page(url)
                    scrape_data = result["scrape_data"]
                    discovered_links = result["discovered_links"]

                    # Build rich metadata with all new fields
                    metadata = {}
                    if scrape_data.metadata:
                        metadata = scrape_data.metadata.model_dump(exclude_none=True)

                    # Merge extra data into metadata for storage
                    if scrape_data.structured_data:
                        metadata["structured_data"] = scrape_data.structured_data
                    if scrape_data.headings:
                        metadata["headings"] = scrape_data.headings
                    if scrape_data.images:
                        metadata["images"] = scrape_data.images
                    if scrape_data.links_detail:
                        metadata["links_detail"] = scrape_data.links_detail

                    # Store result
                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=url,
                            markdown=scrape_data.markdown,
                            html=scrape_data.html,
                            links=scrape_data.links if scrape_data.links else None,
                            metadata_=metadata if metadata else None,
                            screenshot_url=scrape_data.screenshot,  # base64 screenshot
                        )
                        db.add(job_result)

                        pages_crawled += 1

                        # Update job progress
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            job.completed_pages = pages_crawled
                            # Check if cancelled
                            if job.status == "cancelled":
                                await db.commit()
                                break
                        await db.commit()

                    # Add discovered links to frontier
                    await crawler.add_to_frontier(discovered_links, depth + 1)

                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue

            # Mark job as completed with actual page counts
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job and job.status != "cancelled":
                    job.status = "completed"
                    job.total_pages = pages_crawled  # Set to actual count
                    job.completed_pages = pages_crawled
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()
        finally:
            await crawler.cleanup()
            await db_engine.dispose()

    _run_async(_do_crawl())
