"""Request ID middleware for request tracing.

Reads X-Request-ID from the incoming request header or generates a UUID4.
The ID is stored in a contextvars.ContextVar for use in logging and
propagated back as a response header.
"""

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable accessible from anywhere in the same async task
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Read from header or generate
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


def get_request_id() -> str:
    """Get the current request ID (empty string if not in a request context)."""
    return request_id_var.get()
