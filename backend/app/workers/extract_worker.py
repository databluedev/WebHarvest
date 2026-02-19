"""Worker for async /extract jobs (multi-URL extraction)."""

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


@celery_app.task(name="app.workers.extract_worker.process_extract", bind=True, max_retries=1)
def process_extract(self, job_id: str, config: dict):
    """Process a multi-URL extraction job."""

    async def _do_extract():
        from app.core.database import create_worker_session_factory
        from app.models.job import Job
        from app.models.job_result import JobResult
        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url
        from app.services.llm_extract import extract_with_llm
        from app.services.content import html_to_markdown, extract_main_content

        session_factory, db_engine = create_worker_session_factory()

        urls = config.get("urls", [])
        prompt = config.get("prompt")
        schema = config.get("schema_")
        provider = config.get("provider")
        only_main_content = config.get("only_main_content", True)
        wait_for = config.get("wait_for", 0)
        timeout = config.get("timeout", 30000)
        use_proxy = config.get("use_proxy", False)
        custom_headers = config.get("headers")
        custom_cookies = config.get("cookies")
        webhook_url = config.get("webhook_url")
        webhook_secret = config.get("webhook_secret")

        # Load proxy manager if needed
        proxy_manager = None
        if use_proxy:
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
            job.total_pages = len(urls)
            await db.commit()

        try:
            completed = 0
            for url in urls:
                try:
                    # Step 1: Scrape the URL
                    scrape_request = ScrapeRequest(
                        url=url,
                        formats=["markdown"],
                        only_main_content=only_main_content,
                        wait_for=wait_for,
                        timeout=timeout,
                        use_proxy=use_proxy,
                        headers=custom_headers,
                        cookies=custom_cookies,
                    )
                    result = await scrape_url(scrape_request, proxy_manager=proxy_manager)

                    content = result.markdown or ""
                    if not content and result.html:
                        content = html_to_markdown(
                            extract_main_content(result.html, url) if only_main_content else result.html
                        )

                    if not content:
                        raise ValueError(f"No content extracted from {url}")

                    # Step 2: Extract with LLM
                    async with session_factory() as db:
                        job = await db.get(Job, UUID(job_id))
                        user_id = job.user_id if job else None

                    if not user_id:
                        raise ValueError("Job not found")

                    async with session_factory() as db:
                        extract_result = await asyncio.wait_for(
                            extract_with_llm(
                                db=db,
                                user_id=user_id,
                                content=content,
                                prompt=prompt,
                                schema=schema,
                                provider=provider,
                            ),
                            timeout=90,
                        )

                    # Save result
                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=url,
                            markdown=content[:50000] if content else None,
                            extract=extract_result,
                            metadata_={
                                "content_length": len(content),
                                "prompt": prompt,
                                "provider": provider,
                            },
                        )
                        db.add(job_result)
                        completed += 1
                        job = await db.get(Job, UUID(job_id))
                        if job:
                            job.completed_pages = completed
                        await db.commit()

                except Exception as e:
                    logger.warning(f"Extract failed for {url}: {e}")
                    async with session_factory() as db:
                        job_result = JobResult(
                            job_id=UUID(job_id),
                            url=url,
                            metadata_={"error": str(e)},
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
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            # Webhook
            if webhook_url:
                try:
                    from app.services.webhook import send_webhook
                    await send_webhook(
                        url=webhook_url,
                        payload={
                            "event": "job.completed",
                            "job_id": job_id,
                            "job_type": "extract",
                            "status": "completed",
                            "total_urls": len(urls),
                            "completed_urls": completed,
                        },
                        secret=webhook_secret,
                    )
                except Exception as e:
                    logger.warning(f"Webhook failed for extract {job_id}: {e}")

        except Exception as e:
            logger.error(f"Extract job {job_id} failed: {e}")
            async with session_factory() as db:
                job = await db.get(Job, UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            if webhook_url:
                try:
                    from app.services.webhook import send_webhook
                    await send_webhook(
                        url=webhook_url,
                        payload={
                            "event": "job.failed",
                            "job_id": job_id,
                            "job_type": "extract",
                            "error": str(e),
                        },
                        secret=webhook_secret,
                    )
                except Exception:
                    pass
        finally:
            await db_engine.dispose()

    _run_async(_do_extract())
