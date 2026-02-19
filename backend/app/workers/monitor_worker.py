"""Worker for URL change monitoring — checks URLs for content changes."""

import asyncio
import difflib
import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _compute_hash(content: str) -> str:
    """SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _compute_diff_stats(old: str, new: str) -> dict:
    """Compute diff statistics between two strings."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    ratio = sm.ratio()

    opcodes = sm.get_opcodes()
    added = sum(j2 - j1 for tag, i1, i2, j1, j2 in opcodes if tag == "insert")
    removed = sum(i2 - i1 for tag, i1, i2, j1, j2 in opcodes if tag == "delete")
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in opcodes if tag == "replace")

    return {
        "similarity_ratio": round(ratio, 4),
        "added_lines": added,
        "removed_lines": removed,
        "changed_lines": changed,
        "total_old_lines": len(old_lines),
        "total_new_lines": len(new_lines),
    }


def _check_keywords(old_content: str, new_content: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """Check which keywords were added or removed."""
    old_lower = old_content.lower()
    new_lower = new_content.lower()

    found = []
    lost = []

    for kw in keywords:
        kw_lower = kw.lower()
        was_present = kw_lower in old_lower
        is_present = kw_lower in new_lower

        if is_present and not was_present:
            found.append(kw)
        elif was_present and not is_present:
            lost.append(kw)

    return found, lost


@celery_app.task(name="app.workers.monitor_worker.check_monitors")
def check_monitors():
    """Periodic task — check all monitors that are due."""

    async def _check():
        from sqlalchemy import select
        from app.core.database import create_worker_session_factory
        from app.models.monitor import Monitor, MonitorCheck
        from app.schemas.scrape import ScrapeRequest
        from app.services.scraper import scrape_url
        from app.services.content import extract_main_content, html_to_markdown

        session_factory, db_engine = create_worker_session_factory()

        try:
            now = datetime.now(timezone.utc)

            async with session_factory() as db:
                result = await db.execute(
                    select(Monitor).where(
                        Monitor.is_active == True,
                        Monitor.next_check_at <= now,
                    ).limit(50)  # Process max 50 per cycle
                )
                due_monitors = result.scalars().all()

                if not due_monitors:
                    return

                logger.info(f"Checking {len(due_monitors)} monitors")

            for monitor in due_monitors:
                try:
                    await _check_single_monitor(
                        monitor_id=str(monitor.id),
                        session_factory=session_factory,
                    )
                except Exception as e:
                    logger.error(f"Monitor check failed for {monitor.id}: {e}")

        except Exception as e:
            logger.error(f"check_monitors failed: {e}")
        finally:
            await db_engine.dispose()

    _run_async(_check())


@celery_app.task(name="app.workers.monitor_worker.check_single_monitor")
def check_single_monitor_task(monitor_id: str):
    """Check a single monitor on demand."""

    async def _check():
        from app.core.database import create_worker_session_factory

        session_factory, db_engine = create_worker_session_factory()
        try:
            await _check_single_monitor(monitor_id, session_factory)
        finally:
            await db_engine.dispose()

    _run_async(_check())


async def _check_single_monitor(monitor_id: str, session_factory):
    """Core monitor check logic."""
    from bs4 import BeautifulSoup
    from app.models.monitor import Monitor, MonitorCheck
    from app.schemas.scrape import ScrapeRequest
    from app.services.scraper import scrape_url
    from app.services.content import extract_main_content, html_to_markdown

    start_time = time.time()

    async with session_factory() as db:
        monitor = await db.get(Monitor, UUID(monitor_id))
        if not monitor or not monitor.is_active:
            return

        # Scrape the URL
        request = ScrapeRequest(
            url=monitor.url,
            formats=["markdown", "html"],
            only_main_content=monitor.only_main_content,
            headers=monitor.headers,
            cookies=monitor.cookies,
            timeout=30000,
        )

        try:
            result = await asyncio.wait_for(
                scrape_url(request),
                timeout=60,
            )
        except asyncio.TimeoutError:
            # Record timeout check
            check = MonitorCheck(
                monitor_id=monitor.id,
                status_code=0,
                content_hash="",
                has_changed=False,
                change_detail={"change_type": "error", "summary": "Timeout checking URL"},
                response_time_ms=int((time.time() - start_time) * 1000),
            )
            db.add(check)
            monitor.total_checks += 1
            monitor.last_check_at = datetime.now(timezone.utc)
            monitor.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=monitor.check_interval_minutes)
            await db.commit()
            return

        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = result.metadata.status_code if result.metadata else 0

        # Extract content for comparison
        new_content = result.markdown or ""
        if monitor.css_selector and result.html:
            try:
                soup = BeautifulSoup(result.html, "html.parser")
                selected = soup.select(monitor.css_selector)
                if selected:
                    new_content = html_to_markdown(str(selected[0]))
            except Exception:
                pass

        new_hash = _compute_hash(new_content)
        word_count = len(new_content.split()) if new_content else 0

        # Determine if changed
        has_changed = False
        change_detail = None
        old_content = monitor.last_content or ""
        old_hash = monitor.last_content_hash or ""

        if old_hash and new_hash != old_hash:
            # Content changed — compute diff
            diff_stats = _compute_diff_stats(old_content, new_content)
            change_ratio = 1.0 - diff_stats["similarity_ratio"]

            if change_ratio >= monitor.threshold:
                has_changed = True
                change_type = "content_changed"
                summary_parts = []

                if diff_stats["added_lines"]:
                    summary_parts.append(f"+{diff_stats['added_lines']} lines added")
                if diff_stats["removed_lines"]:
                    summary_parts.append(f"-{diff_stats['removed_lines']} lines removed")
                if diff_stats["changed_lines"]:
                    summary_parts.append(f"~{diff_stats['changed_lines']} lines changed")

                summary = ", ".join(summary_parts) or f"Content changed ({change_ratio:.1%} different)"

                change_detail = {
                    "change_type": change_type,
                    "summary": summary,
                    "diff_stats": diff_stats,
                    "old_content_preview": old_content[:500] if old_content else None,
                    "new_content_preview": new_content[:500] if new_content else None,
                }

                # Check keywords if configured
                if monitor.keywords and monitor.notify_on in ("keyword_added", "keyword_removed", "any_change"):
                    found, lost = _check_keywords(old_content, new_content, monitor.keywords)
                    if found:
                        change_detail["keywords_found"] = found
                    if lost:
                        change_detail["keywords_lost"] = lost

                    if monitor.notify_on == "keyword_added" and not found:
                        has_changed = False
                    elif monitor.notify_on == "keyword_removed" and not lost:
                        has_changed = False

        elif monitor.last_status_code and status_code != monitor.last_status_code:
            # Status code changed
            if monitor.notify_on in ("status_change", "any_change"):
                has_changed = True
                change_detail = {
                    "change_type": "status_changed",
                    "summary": f"Status changed from {monitor.last_status_code} to {status_code}",
                    "old_status_code": monitor.last_status_code,
                    "new_status_code": status_code,
                }

        # Record check
        check = MonitorCheck(
            monitor_id=monitor.id,
            status_code=status_code,
            content_hash=new_hash,
            has_changed=has_changed,
            change_detail=change_detail,
            word_count=word_count,
            response_time_ms=elapsed_ms,
        )
        db.add(check)

        # Update monitor state
        monitor.last_check_at = datetime.now(timezone.utc)
        monitor.last_status_code = status_code
        monitor.last_content_hash = new_hash
        monitor.last_content = new_content[:100000]  # Store up to 100k chars
        monitor.total_checks += 1
        monitor.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=monitor.check_interval_minutes)

        if has_changed:
            monitor.last_change_at = datetime.now(timezone.utc)
            monitor.total_changes += 1

        await db.commit()

        # Send webhook if change detected
        if has_changed and monitor.webhook_url:
            try:
                from app.services.webhook import send_webhook
                await send_webhook(
                    url=monitor.webhook_url,
                    payload={
                        "event": "monitor.change",
                        "monitor_id": str(monitor.id),
                        "monitor_name": monitor.name,
                        "url": monitor.url,
                        "change": change_detail,
                        "checked_at": check.checked_at.isoformat(),
                        "status_code": status_code,
                    },
                    secret=monitor.webhook_secret,
                    user_id=str(monitor.user_id),
                )
            except Exception as e:
                logger.warning(f"Monitor webhook failed for {monitor.id}: {e}")
