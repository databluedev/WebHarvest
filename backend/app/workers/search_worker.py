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


@celery_app.task(name="app.workers.search_worker.process_search", bind=True, max_retries=1)
def process_search(self, job_id: str, config: dict):
    """Process a search job — search web, then scrape top results."""

    async def _do_search():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.search import SearchRequest
        from app.schemas.scrape import ScrapeRequest
        from app.services.search import web_search
        from app.services.scraper import scrape_url

        session_factory, db_engine = create_worker_session_factory()
        request = SearchRequest(**config)

        # Load proxy manager if needed
        proxy_manager = None
        if request.use_proxy:
            from app.services.proxy import ProxyManager
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    proxy_manager = await ProxyManager.from_user(db, job.user_id)

        # Update job to running
        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                await db_engine.dispose()
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            # Step 1: Search the web
            search_results = await web_search(
                query=request.query,
                num_results=request.num_results,
                engine=request.engine,
                google_api_key=request.google_api_key,
                google_cx=request.google_cx,
            )

            if not search_results:
                async with session_factory() as db:
                    job = await db.get(Job, UUID(job_id))
                    if job:
                        job.status = "completed"
                        job.total_pages = 0
                        job.completed_pages = 0
                        job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                await db_engine.dispose()
                return

            # Update total count
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.total_pages = len(search_results)
                await db.commit()

            # Step 2: Scrape each search result
            completed = 0
            for sr in search_results:
                try:
                    scrape_request = ScrapeRequest(
                        url=sr.url,
                        formats=request.formats,
                    )
                    result = await scrape_url(scrape_request, proxy_manager=proxy_manager)

                    metadata = {}
                    if result.metadata:
                        metadata = result.metadata.model_dump(exclude_none=True)
                    # Store search snippet in metadata
                    metadata["title"] = sr.title
                    metadata["snippet"] = sr.snippet
                    # Store rich data types in metadata for frontend tabs
                    if result.structured_data:
                        metadata["structured_data"] = result.structured_data
                    if result.headings:
                        metadata["headings"] = result.headings
                    if result.images:
                        metadata["images"] = result.images
                    if result.links_detail:
                        metadata["links_detail"] = result.links_detail

                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=sr.url,
                            markdown=result.markdown,
                            html=result.html,
                            links=result.links if result.links else None,
                            screenshot_url=result.screenshot,
                            metadata_=metadata,
                        )
                        db.add(job_result)

                        completed += 1
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            job.completed_pages = completed
                        await db.commit()

                except Exception as e:
                    logger.warning(f"Failed to scrape search result {sr.url}: {e}")
                    # Store the search result even if scraping fails
                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=sr.url,
                            metadata_={
                                "title": sr.title,
                                "snippet": sr.snippet,
                                "error": str(e),
                            },
                        )
                        db.add(job_result)
                        completed += 1
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            job.completed_pages = completed
                        await db.commit()

            # Mark completed
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.completed_pages = completed
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            logger.error(f"Search job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                await db.commit()
        finally:
            await db_engine.dispose()

    _run_async(_do_search())
