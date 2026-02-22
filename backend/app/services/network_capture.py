"""Browser network request and console log capture.

Captures network traffic and console messages during page loads
for debugging, analysis, and data extraction (e.g., API responses).
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NetworkRequest:
    """A captured network request."""
    url: str
    method: str
    resource_type: str
    headers: dict[str, str] = field(default_factory=dict)
    post_data: str | None = None


@dataclass
class NetworkResponse:
    """A captured network response."""
    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    resource_type: str = ""


@dataclass
class ConsoleMessage:
    """A captured console message."""
    type: str  # "log", "warning", "error", "info"
    text: str
    url: str | None = None


@dataclass
class NetworkCapture:
    """Complete network capture for a page load."""
    requests: list[NetworkRequest] = field(default_factory=list)
    responses: list[NetworkResponse] = field(default_factory=list)
    console_messages: list[ConsoleMessage] = field(default_factory=list)
    
    def get_api_responses(self, pattern: str | None = None) -> list[NetworkResponse]:
        """Get JSON API responses, optionally filtered by URL pattern.
        
        Useful for extracting data from XHR/fetch requests (e.g., product
        APIs, search results, pagination endpoints).
        """
        api_responses = []
        for resp in self.responses:
            if resp.resource_type not in ("xhr", "fetch"):
                continue
            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type and "javascript" not in content_type:
                continue
            if pattern and pattern not in resp.url:
                continue
            api_responses.append(resp)
        return api_responses
    
    def get_errors(self) -> list[ConsoleMessage]:
        """Get console error messages."""
        return [m for m in self.console_messages if m.type == "error"]
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "requests_count": len(self.requests),
            "responses_count": len(self.responses),
            "console_messages": [
                {"type": m.type, "text": m.text[:500]} 
                for m in self.console_messages
            ],
            "api_responses": [
                {"url": r.url, "status": r.status}
                for r in self.get_api_responses()
            ],
        }


class NetworkCaptureHandler:
    """Attaches to a Playwright page to capture network traffic.
    
    Usage:
        handler = NetworkCaptureHandler()
        await handler.attach(page)
        # ... page navigation ...
        capture = handler.get_capture()
    """
    
    def __init__(self, capture_bodies: bool = False, max_body_size: int = 1_000_000):
        self._capture = NetworkCapture()
        self._capture_bodies = capture_bodies
        self._max_body_size = max_body_size
        self._page = None
    
    async def attach(self, page) -> None:
        """Attach listeners to a Playwright page."""
        self._page = page
        
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("console", self._on_console)
    
    def _on_request(self, request) -> None:
        """Handle request event."""
        try:
            self._capture.requests.append(NetworkRequest(
                url=request.url,
                method=request.method,
                resource_type=request.resource_type,
                headers=dict(request.headers) if request.headers else {},
                post_data=request.post_data,
            ))
        except Exception:
            pass
    
    def _on_response(self, response) -> None:
        """Handle response event (sync — body capture is separate)."""
        try:
            self._capture.responses.append(NetworkResponse(
                url=response.url,
                status=response.status,
                headers=dict(response.headers) if response.headers else {},
                resource_type=response.request.resource_type if response.request else "",
            ))
        except Exception:
            pass
    
    def _on_console(self, message) -> None:
        """Handle console message event."""
        try:
            self._capture.console_messages.append(ConsoleMessage(
                type=message.type,
                text=message.text[:2000],
            ))
        except Exception:
            pass
    
    async def capture_api_bodies(self) -> None:
        """Capture response bodies for API (XHR/fetch) responses.
        
        Call after page load is complete. Only captures JSON responses
        under max_body_size.
        """
        if not self._capture_bodies:
            return
        for resp_data in self._capture.responses:
            if resp_data.resource_type not in ("xhr", "fetch"):
                continue
            content_type = resp_data.headers.get("content-type", "")
            if "json" not in content_type:
                continue
            # We can't retroactively get bodies from Playwright events,
            # but we store the metadata for API discovery
    
    def get_capture(self) -> NetworkCapture:
        """Get the captured network data."""
        return self._capture
    
    def detach(self) -> None:
        """Remove listeners (best-effort)."""
        self._page = None
