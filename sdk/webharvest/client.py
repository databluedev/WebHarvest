"""Synchronous and asynchronous clients for the WebHarvest API."""

from __future__ import annotations

import time
from typing import Any

import httpx

from webharvest.exceptions import (
    AuthenticationError,
    JobFailedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    WebHarvestError,
)
from webharvest.models import (
    BatchJob,
    BatchStatus,
    CrawlJob,
    CrawlStatus,
    MapResult,
    Schedule,
    ScheduleList,
    ScheduleRuns,
    ScheduleTrigger,
    ScrapeResult,
    SearchJob,
    SearchStatus,
    TokenResponse,
    TopDomains,
    UsageHistory,
    UsageStats,
    UserInfo,
)

# Terminal statuses for polling loops
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_headers(token: str | None, api_key: str | None) -> dict[str, str]:
    """Build request headers with authentication if available."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _raise_for_status(response: httpx.Response) -> None:
    """Translate HTTP error responses into typed SDK exceptions."""
    if response.is_success:
        return

    try:
        body = response.json()
    except Exception:
        body = {"detail": response.text}

    detail = body.get("detail", f"HTTP {response.status_code}")

    if response.status_code == 401:
        raise AuthenticationError(detail, status_code=401, response_body=body)
    if response.status_code == 404:
        raise NotFoundError(detail, status_code=404, response_body=body)
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        raise RateLimitError(
            detail,
            status_code=429,
            response_body=body,
            retry_after=float(retry_after) if retry_after else None,
        )
    if 500 <= response.status_code < 600:
        raise ServerError(detail, status_code=response.status_code, response_body=body)

    raise WebHarvestError(detail, status_code=response.status_code, response_body=body)


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *d* with all ``None``-valued keys removed."""
    return {k: v for k, v in d.items() if v is not None}


# ===================================================================
# Synchronous client
# ===================================================================


class WebHarvest:
    """Synchronous Python client for the WebHarvest API.

    Example usage::

        from webharvest import WebHarvest

        wh = WebHarvest(api_url="http://localhost:8000")
        wh.login("user@example.com", "password")

        result = wh.scrape("https://example.com")
        print(result.data.markdown)

    Args:
        api_url: Base URL of the WebHarvest API server.
        api_key: Optional API key for authentication. When provided the
            client will send this key as a Bearer token on every request
            and no explicit ``login()`` call is needed.
        timeout: Default HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._token: str | None = None
        self._client = httpx.Client(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return _build_headers(self._token, self._api_key)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Execute an HTTP request and return the decoded JSON body."""
        url = f"{self._api_url}{path}"
        response = self._client.request(
            method,
            url,
            json=json,
            params=params,
            headers=self._headers(),
        )
        _raise_for_status(response)
        return response.json()

    def _get(self, path: str, *, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def _post(self, path: str, *, json: dict | None = None) -> dict:
        return self._request("POST", path, json=json)

    def _put(self, path: str, *, json: dict | None = None) -> dict:
        return self._request("PUT", path, json=json)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate with email and password.

        On success the returned token is stored internally and used for
        all subsequent requests.

        Args:
            email: User email address.
            password: User password.

        Returns:
            A :class:`TokenResponse` containing the access token.

        Raises:
            AuthenticationError: If the credentials are invalid.
        """
        data = self._post("/v1/auth/login", json={"email": email, "password": password})
        token_resp = TokenResponse(**data)
        self._token = token_resp.access_token
        return token_resp

    def register(self, email: str, password: str, name: str | None = None) -> TokenResponse:
        """Register a new user account.

        On success the returned token is stored internally and used for
        all subsequent requests.

        Args:
            email: New user email address.
            password: New user password.
            name: Optional display name.

        Returns:
            A :class:`TokenResponse` containing the access token.
        """
        payload = _strip_none({"email": email, "password": password, "name": name})
        data = self._post("/v1/auth/register", json=payload)
        token_resp = TokenResponse(**data)
        self._token = token_resp.access_token
        return token_resp

    def get_me(self) -> UserInfo:
        """Get the currently authenticated user's profile.

        Returns:
            A :class:`UserInfo` with user details.

        Raises:
            AuthenticationError: If not authenticated.
        """
        data = self._get("/v1/auth/me")
        return UserInfo(**data)

    # ------------------------------------------------------------------
    # Scrape
    # ------------------------------------------------------------------

    def scrape(
        self,
        url: str,
        *,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        extract: dict | None = None,
        use_proxy: bool = False,
    ) -> ScrapeResult:
        """Scrape a single URL and return the result immediately.

        Args:
            url: The URL to scrape.
            formats: Content formats to return (e.g. ``["markdown", "html", "links"]``).
                Defaults to ``["markdown"]`` on the server side.
            only_main_content: If ``True``, strip boilerplate (nav, footer, etc.).
            wait_for: Milliseconds to wait after page load before scraping.
            timeout: Page-load timeout in milliseconds.
            include_tags: CSS selectors to include.
            exclude_tags: CSS selectors to exclude.
            extract: Extraction config with optional ``prompt`` and ``schema_`` keys.
            use_proxy: Route the request through a configured proxy.

        Returns:
            A :class:`ScrapeResult` with the scraped data.
        """
        payload: dict[str, Any] = {
            "url": url,
            "only_main_content": only_main_content,
            "wait_for": wait_for,
            "timeout": timeout,
            "use_proxy": use_proxy,
        }
        if formats is not None:
            payload["formats"] = formats
        if include_tags is not None:
            payload["include_tags"] = include_tags
        if exclude_tags is not None:
            payload["exclude_tags"] = exclude_tags
        if extract is not None:
            payload["extract"] = extract
        data = self._post("/v1/scrape", json=payload)
        return ScrapeResult(**data)

    # ------------------------------------------------------------------
    # Crawl
    # ------------------------------------------------------------------

    def start_crawl(
        self,
        url: str,
        *,
        max_pages: int = 100,
        max_depth: int = 3,
        concurrency: int = 3,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        allow_external_links: bool = False,
        respect_robots_txt: bool = True,
        scrape_options: dict | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> CrawlJob:
        """Start an asynchronous crawl job.

        The job runs in the background. Use :meth:`get_crawl_status` to
        poll for completion, or use :meth:`crawl` for a blocking variant.

        Args:
            url: Seed URL for the crawl.
            max_pages: Maximum number of pages to crawl.
            max_depth: Maximum link depth from the seed URL.
            concurrency: Number of concurrent scrapers (1--10).
            include_paths: Glob patterns for URLs to include.
            exclude_paths: Glob patterns for URLs to exclude.
            allow_external_links: Whether to follow links to other domains.
            respect_robots_txt: Whether to respect robots.txt.
            scrape_options: Per-page scrape settings (formats, wait_for, etc.).
            use_proxy: Route requests through a configured proxy.
            webhook_url: URL to POST a notification to when the job finishes.
            webhook_secret: Secret used to sign webhook payloads.

        Returns:
            A :class:`CrawlJob` with the ``job_id``.
        """
        payload: dict[str, Any] = {
            "url": url,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "concurrency": concurrency,
            "allow_external_links": allow_external_links,
            "respect_robots_txt": respect_robots_txt,
            "use_proxy": use_proxy,
        }
        if include_paths is not None:
            payload["include_paths"] = include_paths
        if exclude_paths is not None:
            payload["exclude_paths"] = exclude_paths
        if scrape_options is not None:
            payload["scrape_options"] = scrape_options
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = self._post("/v1/crawl", json=payload)
        return CrawlJob(**data)

    def get_crawl_status(self, job_id: str) -> CrawlStatus:
        """Get the current status and results for a crawl job.

        Args:
            job_id: The job identifier returned by :meth:`start_crawl`.

        Returns:
            A :class:`CrawlStatus` with progress info and scraped data.

        Raises:
            NotFoundError: If the job does not exist.
        """
        data = self._get(f"/v1/crawl/{job_id}")
        return CrawlStatus(**data)

    def cancel_crawl(self, job_id: str) -> dict:
        """Cancel a running crawl job.

        Args:
            job_id: The job identifier.

        Returns:
            A dict with ``success`` and ``message`` keys.
        """
        return self._delete(f"/v1/crawl/{job_id}")

    def crawl(
        self,
        url: str,
        *,
        max_pages: int = 100,
        max_depth: int = 3,
        concurrency: int = 3,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        allow_external_links: bool = False,
        respect_robots_txt: bool = True,
        scrape_options: dict | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        timeout: float = 300,
    ) -> CrawlStatus:
        """Start a crawl and poll until it completes.

        This is a convenience wrapper around :meth:`start_crawl` and
        :meth:`get_crawl_status` that blocks until the job reaches a
        terminal status.

        All crawl-related parameters are forwarded to :meth:`start_crawl`.

        Args:
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait before raising :class:`TimeoutError`.

        Returns:
            The final :class:`CrawlStatus`.

        Raises:
            TimeoutError: If the job does not finish within *timeout* seconds.
            JobFailedError: If the job finishes with a ``failed`` status.
        """
        job = self.start_crawl(
            url,
            max_pages=max_pages,
            max_depth=max_depth,
            concurrency=concurrency,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
            allow_external_links=allow_external_links,
            respect_robots_txt=respect_robots_txt,
            scrape_options=scrape_options,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return self._poll_crawl(job.job_id, poll_interval=poll_interval, timeout=timeout)

    def _poll_crawl(self, job_id: str, *, poll_interval: float, timeout: float) -> CrawlStatus:
        start = time.monotonic()
        while True:
            status = self.get_crawl_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Crawl job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Crawl job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def start_batch(
        self,
        urls: list[str] | None = None,
        *,
        items: list[dict] | None = None,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        concurrency: int = 5,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> BatchJob:
        """Start an asynchronous batch scrape job.

        Provide either a simple list of *urls* or a list of *items* with
        per-URL overrides (but not both).

        Args:
            urls: Simple list of URLs to scrape.
            items: Per-URL configuration dicts.
            formats: Content formats to return.
            only_main_content: Strip boilerplate.
            wait_for: Wait after page load (ms).
            timeout: Page-load timeout (ms).
            concurrency: Max concurrent scrapers.
            use_proxy: Use a configured proxy.
            webhook_url: Webhook notification URL.
            webhook_secret: Webhook signing secret.

        Returns:
            A :class:`BatchJob` with the ``job_id`` and ``total_urls``.
        """
        payload: dict[str, Any] = {
            "only_main_content": only_main_content,
            "wait_for": wait_for,
            "timeout": timeout,
            "concurrency": concurrency,
            "use_proxy": use_proxy,
        }
        if urls is not None:
            payload["urls"] = urls
        if items is not None:
            payload["items"] = items
        if formats is not None:
            payload["formats"] = formats
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = self._post("/v1/batch/scrape", json=payload)
        return BatchJob(**data)

    def get_batch_status(self, job_id: str) -> BatchStatus:
        """Get the current status and results for a batch scrape job.

        Args:
            job_id: The job identifier returned by :meth:`start_batch`.

        Returns:
            A :class:`BatchStatus`.
        """
        data = self._get(f"/v1/batch/{job_id}")
        return BatchStatus(**data)

    def batch(
        self,
        urls: list[str] | None = None,
        *,
        items: list[dict] | None = None,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        concurrency: int = 5,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        poll_timeout: float = 300,
    ) -> BatchStatus:
        """Start a batch scrape and poll until it completes.

        Convenience wrapper that blocks until the job reaches a terminal
        status. All batch-related parameters are forwarded to
        :meth:`start_batch`.

        Args:
            poll_interval: Seconds between status polls.
            poll_timeout: Maximum seconds to wait.

        Returns:
            The final :class:`BatchStatus`.

        Raises:
            TimeoutError: If the job does not finish in time.
            JobFailedError: If the job fails.
        """
        job = self.start_batch(
            urls,
            items=items,
            formats=formats,
            only_main_content=only_main_content,
            wait_for=wait_for,
            timeout=timeout,
            concurrency=concurrency,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return self._poll_batch(job.job_id, poll_interval=poll_interval, timeout=poll_timeout)

    def _poll_batch(self, job_id: str, *, poll_interval: float, timeout: float) -> BatchStatus:
        start = time.monotonic()
        while True:
            status = self.get_batch_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Batch job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Batch job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def start_search(
        self,
        query: str,
        *,
        num_results: int = 5,
        engine: str = "duckduckgo",
        google_api_key: str | None = None,
        google_cx: str | None = None,
        brave_api_key: str | None = None,
        formats: list[str] | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> SearchJob:
        """Start an asynchronous search-and-scrape job.

        The engine searches the web, then scrapes each result page.

        Args:
            query: Search query string.
            num_results: How many search results to scrape.
            engine: Search engine to use (``duckduckgo``, ``google``, or ``brave``).
            google_api_key: API key for Google Custom Search.
            google_cx: Google Custom Search Engine ID.
            brave_api_key: API key for Brave Search.
            formats: Content formats to return.
            use_proxy: Use a configured proxy.
            webhook_url: Webhook notification URL.
            webhook_secret: Webhook signing secret.

        Returns:
            A :class:`SearchJob` with the ``job_id``.
        """
        payload: dict[str, Any] = {
            "query": query,
            "num_results": num_results,
            "engine": engine,
            "use_proxy": use_proxy,
        }
        if google_api_key is not None:
            payload["google_api_key"] = google_api_key
        if google_cx is not None:
            payload["google_cx"] = google_cx
        if brave_api_key is not None:
            payload["brave_api_key"] = brave_api_key
        if formats is not None:
            payload["formats"] = formats
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = self._post("/v1/search", json=payload)
        return SearchJob(**data)

    def get_search_status(self, job_id: str) -> SearchStatus:
        """Get the current status and results for a search job.

        Args:
            job_id: The job identifier returned by :meth:`start_search`.

        Returns:
            A :class:`SearchStatus`.
        """
        data = self._get(f"/v1/search/{job_id}")
        return SearchStatus(**data)

    def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        engine: str = "duckduckgo",
        google_api_key: str | None = None,
        google_cx: str | None = None,
        brave_api_key: str | None = None,
        formats: list[str] | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        timeout: float = 300,
    ) -> SearchStatus:
        """Start a search and poll until it completes.

        Convenience wrapper that blocks until the job reaches a terminal
        status. All search parameters are forwarded to :meth:`start_search`.

        Args:
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.

        Returns:
            The final :class:`SearchStatus`.

        Raises:
            TimeoutError: If the job does not finish in time.
            JobFailedError: If the job fails.
        """
        job = self.start_search(
            query,
            num_results=num_results,
            engine=engine,
            google_api_key=google_api_key,
            google_cx=google_cx,
            brave_api_key=brave_api_key,
            formats=formats,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return self._poll_search(job.job_id, poll_interval=poll_interval, timeout=timeout)

    def _poll_search(self, job_id: str, *, poll_interval: float, timeout: float) -> SearchStatus:
        start = time.monotonic()
        while True:
            status = self.get_search_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Search job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Search job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------

    def map(
        self,
        url: str,
        *,
        search: str | None = None,
        limit: int = 100,
        include_subdomains: bool = True,
        use_sitemap: bool = True,
    ) -> MapResult:
        """Discover all URLs on a site via sitemap and link crawling.

        Args:
            url: The root URL of the site to map.
            search: Optional search filter to narrow returned links.
            limit: Maximum number of links to return.
            include_subdomains: Whether to include subdomain links.
            use_sitemap: Whether to parse the site's sitemap.xml.

        Returns:
            A :class:`MapResult` with the discovered links.
        """
        payload: dict[str, Any] = {
            "url": url,
            "limit": limit,
            "include_subdomains": include_subdomains,
            "use_sitemap": use_sitemap,
        }
        if search is not None:
            payload["search"] = search

        data = self._post("/v1/map", json=payload)
        return MapResult(**data)

    # ------------------------------------------------------------------
    # Usage / Analytics
    # ------------------------------------------------------------------

    def get_usage_stats(self) -> UsageStats:
        """Get aggregate usage statistics for the current user.

        Returns:
            A :class:`UsageStats` with totals, averages, and breakdowns.
        """
        data = self._get("/v1/usage/stats")
        return UsageStats(**data)

    def get_usage_history(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> UsageHistory:
        """Get paginated job history with optional filters.

        Args:
            page: Page number (1-indexed).
            per_page: Results per page (max 100).
            type: Filter by job type (``scrape``, ``crawl``, ``batch``, ``search``).
            status: Filter by status (``pending``, ``running``, ``completed``, ``failed``).
            search: Free-text search across job URLs/queries.
            sort_by: Column to sort by (``created_at``, ``completed_at``, ``status``, ``type``).
            sort_dir: Sort direction (``asc`` or ``desc``).

        Returns:
            A :class:`UsageHistory` with paginated job entries.
        """
        params = _strip_none(
            {
                "page": page,
                "per_page": per_page,
                "type": type,
                "status": status,
                "search": search,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
        )
        data = self._get("/v1/usage/history", params=params)
        return UsageHistory(**data)

    def get_top_domains(self, *, limit: int = 20) -> TopDomains:
        """Get the most frequently scraped domains.

        Args:
            limit: Maximum number of domains to return.

        Returns:
            A :class:`TopDomains` with domain counts.
        """
        data = self._get("/v1/usage/top-domains", params={"limit": limit})
        return TopDomains(**data)

    def delete_job(self, job_id: str) -> dict:
        """Delete a job and all its results.

        Args:
            job_id: The job identifier.

        Returns:
            A dict with ``success`` and ``message`` keys.
        """
        return self._delete(f"/v1/usage/jobs/{job_id}")

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def create_schedule(
        self,
        name: str,
        schedule_type: str,
        config: dict[str, Any],
        cron_expression: str,
        *,
        timezone: str = "UTC",
        webhook_url: str | None = None,
    ) -> Schedule:
        """Create a new recurring schedule.

        Args:
            name: Human-readable name for the schedule.
            schedule_type: One of ``scrape``, ``crawl``, or ``batch``.
            config: Job configuration dict (the same payload you would pass
                to the corresponding start endpoint).
            cron_expression: Cron expression defining the recurrence.
            timezone: Timezone for cron evaluation (default ``UTC``).
            webhook_url: Optional webhook notification URL.

        Returns:
            The created :class:`Schedule`.
        """
        payload: dict[str, Any] = {
            "name": name,
            "schedule_type": schedule_type,
            "config": config,
            "cron_expression": cron_expression,
            "timezone": timezone,
        }
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url

        data = self._post("/v1/schedules", json=payload)
        return Schedule(**data)

    def list_schedules(self) -> ScheduleList:
        """List all schedules for the current user.

        Returns:
            A :class:`ScheduleList`.
        """
        data = self._get("/v1/schedules")
        return ScheduleList(**data)

    def get_schedule(self, schedule_id: str) -> Schedule:
        """Get a single schedule by ID.

        Args:
            schedule_id: The schedule identifier.

        Returns:
            The :class:`Schedule`.

        Raises:
            NotFoundError: If the schedule does not exist.
        """
        data = self._get(f"/v1/schedules/{schedule_id}")
        return Schedule(**data)

    def get_schedule_runs(self, schedule_id: str) -> ScheduleRuns:
        """Get recent runs for a schedule.

        Args:
            schedule_id: The schedule identifier.

        Returns:
            A :class:`ScheduleRuns` with the run history.
        """
        data = self._get(f"/v1/schedules/{schedule_id}/runs")
        return ScheduleRuns(**data)

    def update_schedule(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        cron_expression: str | None = None,
        timezone: str | None = None,
        is_active: bool | None = None,
        config: dict[str, Any] | None = None,
        webhook_url: str | None = None,
    ) -> Schedule:
        """Update an existing schedule.

        Only provided fields are updated; ``None`` values are omitted.

        Args:
            schedule_id: The schedule identifier.
            name: New name.
            cron_expression: New cron expression.
            timezone: New timezone.
            is_active: Enable or disable the schedule.
            config: New job configuration.
            webhook_url: New webhook URL.

        Returns:
            The updated :class:`Schedule`.
        """
        payload = _strip_none(
            {
                "name": name,
                "cron_expression": cron_expression,
                "timezone": timezone,
                "is_active": is_active,
                "config": config,
                "webhook_url": webhook_url,
            }
        )
        data = self._put(f"/v1/schedules/{schedule_id}", json=payload)
        return Schedule(**data)

    def delete_schedule(self, schedule_id: str) -> dict:
        """Delete a schedule.

        Args:
            schedule_id: The schedule identifier.

        Returns:
            A dict with ``success`` and ``message`` keys.
        """
        return self._delete(f"/v1/schedules/{schedule_id}")

    def trigger_schedule(self, schedule_id: str) -> ScheduleTrigger:
        """Manually trigger a schedule to run immediately.

        Args:
            schedule_id: The schedule identifier.

        Returns:
            A :class:`ScheduleTrigger` with the created ``job_id``.
        """
        data = self._post(f"/v1/schedules/{schedule_id}/trigger")
        return ScheduleTrigger(**data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> WebHarvest:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ===================================================================
# Asynchronous client
# ===================================================================


class AsyncWebHarvest:
    """Asynchronous Python client for the WebHarvest API.

    This class mirrors every method of :class:`WebHarvest` but uses
    ``httpx.AsyncClient`` and ``async``/``await`` syntax.

    Example usage::

        import asyncio
        from webharvest import AsyncWebHarvest

        async def main():
            async with AsyncWebHarvest() as wh:
                await wh.login("user@example.com", "password")
                result = await wh.scrape("https://example.com")
                print(result.data.markdown)

        asyncio.run(main())

    Args:
        api_url: Base URL of the WebHarvest API server.
        api_key: Optional API key for authentication.
        timeout: Default HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return _build_headers(self._token, self._api_key)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        url = f"{self._api_url}{path}"
        response = await self._client.request(
            method,
            url,
            json=json,
            params=params,
            headers=self._headers(),
        )
        _raise_for_status(response)
        return response.json()

    async def _get(self, path: str, *, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, *, json: dict | None = None) -> dict:
        return await self._request("POST", path, json=json)

    async def _put(self, path: str, *, json: dict | None = None) -> dict:
        return await self._request("PUT", path, json=json)

    async def _delete(self, path: str) -> dict:
        return await self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate with email and password.

        On success the returned token is stored internally and used for
        all subsequent requests.
        """
        data = await self._post("/v1/auth/login", json={"email": email, "password": password})
        token_resp = TokenResponse(**data)
        self._token = token_resp.access_token
        return token_resp

    async def register(self, email: str, password: str, name: str | None = None) -> TokenResponse:
        """Register a new user account."""
        payload = _strip_none({"email": email, "password": password, "name": name})
        data = await self._post("/v1/auth/register", json=payload)
        token_resp = TokenResponse(**data)
        self._token = token_resp.access_token
        return token_resp

    async def get_me(self) -> UserInfo:
        """Get the currently authenticated user's profile."""
        data = await self._get("/v1/auth/me")
        return UserInfo(**data)

    # ------------------------------------------------------------------
    # Scrape
    # ------------------------------------------------------------------

    async def scrape(
        self,
        url: str,
        *,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        extract: dict | None = None,
        use_proxy: bool = False,
    ) -> ScrapeResult:
        """Scrape a single URL and return the result immediately."""
        payload: dict[str, Any] = {
            "url": url,
            "only_main_content": only_main_content,
            "wait_for": wait_for,
            "timeout": timeout,
            "use_proxy": use_proxy,
        }
        if formats is not None:
            payload["formats"] = formats
        if include_tags is not None:
            payload["include_tags"] = include_tags
        if exclude_tags is not None:
            payload["exclude_tags"] = exclude_tags
        if extract is not None:
            payload["extract"] = extract
        data = await self._post("/v1/scrape", json=payload)
        return ScrapeResult(**data)

    # ------------------------------------------------------------------
    # Crawl
    # ------------------------------------------------------------------

    async def start_crawl(
        self,
        url: str,
        *,
        max_pages: int = 100,
        max_depth: int = 3,
        concurrency: int = 3,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        allow_external_links: bool = False,
        respect_robots_txt: bool = True,
        scrape_options: dict | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> CrawlJob:
        """Start an asynchronous crawl job."""
        payload: dict[str, Any] = {
            "url": url,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "concurrency": concurrency,
            "allow_external_links": allow_external_links,
            "respect_robots_txt": respect_robots_txt,
            "use_proxy": use_proxy,
        }
        if include_paths is not None:
            payload["include_paths"] = include_paths
        if exclude_paths is not None:
            payload["exclude_paths"] = exclude_paths
        if scrape_options is not None:
            payload["scrape_options"] = scrape_options
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = await self._post("/v1/crawl", json=payload)
        return CrawlJob(**data)

    async def get_crawl_status(self, job_id: str) -> CrawlStatus:
        """Get the current status and results for a crawl job."""
        data = await self._get(f"/v1/crawl/{job_id}")
        return CrawlStatus(**data)

    async def cancel_crawl(self, job_id: str) -> dict:
        """Cancel a running crawl job."""
        return await self._delete(f"/v1/crawl/{job_id}")

    async def crawl(
        self,
        url: str,
        *,
        max_pages: int = 100,
        max_depth: int = 3,
        concurrency: int = 3,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        allow_external_links: bool = False,
        respect_robots_txt: bool = True,
        scrape_options: dict | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        timeout: float = 300,
    ) -> CrawlStatus:
        """Start a crawl and poll until it completes."""
        job = await self.start_crawl(
            url,
            max_pages=max_pages,
            max_depth=max_depth,
            concurrency=concurrency,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
            allow_external_links=allow_external_links,
            respect_robots_txt=respect_robots_txt,
            scrape_options=scrape_options,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return await self._poll_crawl(job.job_id, poll_interval=poll_interval, timeout=timeout)

    async def _poll_crawl(self, job_id: str, *, poll_interval: float, timeout: float) -> CrawlStatus:
        import asyncio

        start = time.monotonic()
        while True:
            status = await self.get_crawl_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Crawl job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Crawl job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    async def start_batch(
        self,
        urls: list[str] | None = None,
        *,
        items: list[dict] | None = None,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        concurrency: int = 5,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> BatchJob:
        """Start an asynchronous batch scrape job."""
        payload: dict[str, Any] = {
            "only_main_content": only_main_content,
            "wait_for": wait_for,
            "timeout": timeout,
            "concurrency": concurrency,
            "use_proxy": use_proxy,
        }
        if urls is not None:
            payload["urls"] = urls
        if items is not None:
            payload["items"] = items
        if formats is not None:
            payload["formats"] = formats
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = await self._post("/v1/batch/scrape", json=payload)
        return BatchJob(**data)

    async def get_batch_status(self, job_id: str) -> BatchStatus:
        """Get the current status and results for a batch scrape job."""
        data = await self._get(f"/v1/batch/{job_id}")
        return BatchStatus(**data)

    async def batch(
        self,
        urls: list[str] | None = None,
        *,
        items: list[dict] | None = None,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int = 0,
        timeout: int = 30000,
        concurrency: int = 5,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        poll_timeout: float = 300,
    ) -> BatchStatus:
        """Start a batch scrape and poll until it completes."""
        job = await self.start_batch(
            urls,
            items=items,
            formats=formats,
            only_main_content=only_main_content,
            wait_for=wait_for,
            timeout=timeout,
            concurrency=concurrency,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return await self._poll_batch(job.job_id, poll_interval=poll_interval, timeout=poll_timeout)

    async def _poll_batch(self, job_id: str, *, poll_interval: float, timeout: float) -> BatchStatus:
        import asyncio

        start = time.monotonic()
        while True:
            status = await self.get_batch_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Batch job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Batch job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def start_search(
        self,
        query: str,
        *,
        num_results: int = 5,
        engine: str = "duckduckgo",
        google_api_key: str | None = None,
        google_cx: str | None = None,
        brave_api_key: str | None = None,
        formats: list[str] | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> SearchJob:
        """Start an asynchronous search-and-scrape job."""
        payload: dict[str, Any] = {
            "query": query,
            "num_results": num_results,
            "engine": engine,
            "use_proxy": use_proxy,
        }
        if google_api_key is not None:
            payload["google_api_key"] = google_api_key
        if google_cx is not None:
            payload["google_cx"] = google_cx
        if brave_api_key is not None:
            payload["brave_api_key"] = brave_api_key
        if formats is not None:
            payload["formats"] = formats
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if webhook_secret is not None:
            payload["webhook_secret"] = webhook_secret

        data = await self._post("/v1/search", json=payload)
        return SearchJob(**data)

    async def get_search_status(self, job_id: str) -> SearchStatus:
        """Get the current status and results for a search job."""
        data = await self._get(f"/v1/search/{job_id}")
        return SearchStatus(**data)

    async def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        engine: str = "duckduckgo",
        google_api_key: str | None = None,
        google_cx: str | None = None,
        brave_api_key: str | None = None,
        formats: list[str] | None = None,
        use_proxy: bool = False,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        poll_interval: float = 2,
        timeout: float = 300,
    ) -> SearchStatus:
        """Start a search and poll until it completes."""
        job = await self.start_search(
            query,
            num_results=num_results,
            engine=engine,
            google_api_key=google_api_key,
            google_cx=google_cx,
            brave_api_key=brave_api_key,
            formats=formats,
            use_proxy=use_proxy,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        return await self._poll_search(job.job_id, poll_interval=poll_interval, timeout=timeout)

    async def _poll_search(self, job_id: str, *, poll_interval: float, timeout: float) -> SearchStatus:
        import asyncio

        start = time.monotonic()
        while True:
            status = await self.get_search_status(job_id)
            if status.status in _TERMINAL_STATUSES:
                if status.status == "failed":
                    raise JobFailedError(
                        status.error or "Search job failed",
                        job_id=job_id,
                        response_body=status.model_dump(),
                    )
                return status
            elapsed = time.monotonic() - start
            if elapsed + poll_interval > timeout:
                raise TimeoutError(
                    f"Search job {job_id} did not complete within {timeout}s",
                    job_id=job_id,
                    elapsed=elapsed,
                )
            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------

    async def map(
        self,
        url: str,
        *,
        search: str | None = None,
        limit: int = 100,
        include_subdomains: bool = True,
        use_sitemap: bool = True,
    ) -> MapResult:
        """Discover all URLs on a site via sitemap and link crawling."""
        payload: dict[str, Any] = {
            "url": url,
            "limit": limit,
            "include_subdomains": include_subdomains,
            "use_sitemap": use_sitemap,
        }
        if search is not None:
            payload["search"] = search

        data = await self._post("/v1/map", json=payload)
        return MapResult(**data)

    # ------------------------------------------------------------------
    # Usage / Analytics
    # ------------------------------------------------------------------

    async def get_usage_stats(self) -> UsageStats:
        """Get aggregate usage statistics for the current user."""
        data = await self._get("/v1/usage/stats")
        return UsageStats(**data)

    async def get_usage_history(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> UsageHistory:
        """Get paginated job history with optional filters."""
        params = _strip_none(
            {
                "page": page,
                "per_page": per_page,
                "type": type,
                "status": status,
                "search": search,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
        )
        data = await self._get("/v1/usage/history", params=params)
        return UsageHistory(**data)

    async def get_top_domains(self, *, limit: int = 20) -> TopDomains:
        """Get the most frequently scraped domains."""
        data = await self._get("/v1/usage/top-domains", params={"limit": limit})
        return TopDomains(**data)

    async def delete_job(self, job_id: str) -> dict:
        """Delete a job and all its results."""
        return await self._delete(f"/v1/usage/jobs/{job_id}")

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    async def create_schedule(
        self,
        name: str,
        schedule_type: str,
        config: dict[str, Any],
        cron_expression: str,
        *,
        timezone: str = "UTC",
        webhook_url: str | None = None,
    ) -> Schedule:
        """Create a new recurring schedule."""
        payload: dict[str, Any] = {
            "name": name,
            "schedule_type": schedule_type,
            "config": config,
            "cron_expression": cron_expression,
            "timezone": timezone,
        }
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url

        data = await self._post("/v1/schedules", json=payload)
        return Schedule(**data)

    async def list_schedules(self) -> ScheduleList:
        """List all schedules for the current user."""
        data = await self._get("/v1/schedules")
        return ScheduleList(**data)

    async def get_schedule(self, schedule_id: str) -> Schedule:
        """Get a single schedule by ID."""
        data = await self._get(f"/v1/schedules/{schedule_id}")
        return Schedule(**data)

    async def get_schedule_runs(self, schedule_id: str) -> ScheduleRuns:
        """Get recent runs for a schedule."""
        data = await self._get(f"/v1/schedules/{schedule_id}/runs")
        return ScheduleRuns(**data)

    async def update_schedule(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        cron_expression: str | None = None,
        timezone: str | None = None,
        is_active: bool | None = None,
        config: dict[str, Any] | None = None,
        webhook_url: str | None = None,
    ) -> Schedule:
        """Update an existing schedule."""
        payload = _strip_none(
            {
                "name": name,
                "cron_expression": cron_expression,
                "timezone": timezone,
                "is_active": is_active,
                "config": config,
                "webhook_url": webhook_url,
            }
        )
        data = await self._put(f"/v1/schedules/{schedule_id}", json=payload)
        return Schedule(**data)

    async def delete_schedule(self, schedule_id: str) -> dict:
        """Delete a schedule."""
        return await self._delete(f"/v1/schedules/{schedule_id}")

    async def trigger_schedule(self, schedule_id: str) -> ScheduleTrigger:
        """Manually trigger a schedule to run immediately."""
        data = await self._post(f"/v1/schedules/{schedule_id}/trigger")
        return ScheduleTrigger(**data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncWebHarvest:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
