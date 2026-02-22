import asyncio
import logging
import time as _time_mod
from datetime import datetime, timezone
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_WORKER_NAME = "search"


def _run_async(coro):
    from app.services.scraper import reset_pool_state_sync
    reset_pool_state_sync()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            from app.services.scraper import cleanup_async_pools
            loop.run_until_complete(cleanup_async_pools())
        except Exception:
            pass
        loop.close()


@celery_app.task(
    name="app.workers.search_worker.process_search",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=3600,
    time_limit=3660,
)
def process_search(self, job_id: str, config: dict):
    """Process a search job — search web, then scrape top results."""
    from app.core.metrics import worker_task_total, worker_task_duration_seconds, worker_active_tasks

    _start = _time_mod.monotonic()
    worker_active_tasks.labels(worker=_WORKER_NAME).inc()

    async def _do_search():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.search import SearchRequest
        from app.schemas.scrape import ScrapeRequest
        from app.services.search import web_search
        from app.services.scraper import scrape_url
        from app.services.llm_extract import extract_with_llm
        from app.services.dedup import deduplicate_urls

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

        # Update job to running and capture user_id
        user_id = None
        async with session_factory() as db:
            job = await db.get(Job, UUID(job_id))
            if not job:
                await db_engine.dispose()
                return
            user_id = job.user_id
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            # Cross-user cache check
            from app.core.cache import get_cached_search, set_cached_search
            cached_search = await get_cached_search(
                request.query, request.num_results, request.engine, request.formats,
            )
            if cached_search:
                logger.info(f"Search cache hit for '{request.query}' ({len(cached_search)} results)")
                async with session_factory() as db:
                    for item in cached_search:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=item["url"],
                            markdown=item.get("markdown"),
                            html=item.get("html"),
                            links=item.get("links"),
                            extract=item.get("extract"),
                            screenshot_url=item.get("screenshot"),
                            metadata_=item.get("metadata"),
                        )
                        db.add(job_result)
                    job = await db.get(Job, UUID(job_id))
                    if job:
                        job.status = "completed"
                        job.total_pages = len(cached_search)
                        job.completed_pages = len(cached_search)
                        job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                await db_engine.dispose()
                return

            # Step 1: Search the web
            search_results = await web_search(
                query=request.query,
                num_results=request.num_results,
                engine=request.engine,
                google_api_key=request.google_api_key,
                google_cx=request.google_cx,
                brave_api_key=request.brave_api_key,
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

            # Deduplicate search result URLs
            deduped_urls = deduplicate_urls([sr.url for sr in search_results])
            # Rebuild search_results in deduped order
            deduped_results = []
            seen_norm = set()
            for url in deduped_urls:
                for sr in search_results:
                    if sr.url == url and sr.url not in seen_norm:
                        deduped_results.append(sr)
                        seen_norm.add(sr.url)
                        break
            search_results = deduped_results

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
                        only_main_content=request.only_main_content,
                        use_proxy=request.use_proxy,
                        headers=request.headers,
                        cookies=request.cookies,
                        mobile=request.mobile,
                        mobile_device=request.mobile_device,
                    )
                    result = await asyncio.wait_for(
                        scrape_url(scrape_request, proxy_manager=proxy_manager),
                        timeout=120,
                    )

                    _req_fmts = set(request.formats)

                    metadata = {}
                    if result.metadata:
                        metadata = result.metadata.model_dump(exclude_none=True)
                    # Store search snippet in metadata
                    metadata["title"] = sr.title
                    metadata["snippet"] = sr.snippet
                    # Store rich data types in metadata — only if user requested them
                    if result.structured_data and (not _req_fmts or "structured_data" in _req_fmts):
                        metadata["structured_data"] = result.structured_data
                    if result.headings and (not _req_fmts or "headings" in _req_fmts):
                        metadata["headings"] = result.headings
                    if result.images and (not _req_fmts or "images" in _req_fmts):
                        metadata["images"] = result.images
                    if result.links_detail and (not _req_fmts or "links" in _req_fmts):
                        metadata["links_detail"] = result.links_detail

                    # LLM extraction if configured
                    extract_data = None
                    if request.extract and result.markdown:
                        try:
                            async with session_factory() as llm_db:
                                extract_data = await asyncio.wait_for(
                                    extract_with_llm(
                                        db=llm_db,
                                        user_id=user_id,
                                        content=result.markdown,
                                        prompt=request.extract.prompt,
                                        schema=request.extract.schema_,
                                    ),
                                    timeout=90,
                                )
                        except Exception as e:
                            logger.warning(f"LLM extraction failed for {sr.url}: {e}")

                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=sr.url,
                            markdown=result.markdown if not _req_fmts or "markdown" in _req_fmts else None,
                            html=result.html if not _req_fmts or "html" in _req_fmts else None,
                            links=result.links if result.links and (not _req_fmts or "links" in _req_fmts) else None,
                            extract=extract_data,
                            screenshot_url=result.screenshot if not _req_fmts or "screenshot" in _req_fmts else None,
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

            # Cache the search results for other users
            try:
                cache_data = []
                async with session_factory() as db:
                    from sqlalchemy import select
                    result = await db.execute(
                        select(JobResult).where(JobResult.job_id == UUID(job_id))
                    )
                    for jr in result.scalars().all():
                        cache_data.append({
                            "url": jr.url,
                            "markdown": jr.markdown,
                            "html": jr.html,
                            "links": jr.links,
                            "extract": jr.extract,
                            "screenshot": jr.screenshot_url,
                            "metadata": jr.metadata_,
                        })
                if cache_data:
                    await set_cached_search(
                        request.query, request.num_results, request.engine,
                        request.formats, cache_data,
                    )
            except Exception as e:
                logger.warning(f"Failed to cache search results for '{request.query}': {e}")

            # Mark completed
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "completed"
                    job.completed_pages = completed
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
                                    "event": "job.completed",
                                    "job_id": job_id,
                                    "job_type": "search",
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
                    logger.warning(f"Webhook delivery failed for search {job_id}: {e}")

        except Exception as e:
            logger.error(f"Search job {job_id} failed: {e}")
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
                            "job_type": "search",
                            "status": "failed",
                            "error": str(e),
                        },
                        secret=request.webhook_secret,
                    )
                except Exception:
                    pass
        finally:
            await db_engine.dispose()

    try:
        _run_async(_do_search())
        worker_task_total.labels(worker=_WORKER_NAME, status="success").inc()
    except Exception:
        worker_task_total.labels(worker=_WORKER_NAME, status="failure").inc()
        raise
    finally:
        worker_active_tasks.labels(worker=_WORKER_NAME).dec()
        worker_task_duration_seconds.labels(worker=_WORKER_NAME).observe(
            _time_mod.monotonic() - _start
        )
