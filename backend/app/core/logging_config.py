"""Structured logging configuration.

Supports two modes via LOG_FORMAT env var:
- "json" (default for production): JSON-formatted log lines with request_id
- "text" (for development): Human-readable log lines
"""

import logging
import sys

from app.middleware.request_id import get_request_id


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


def configure_logging(log_format: str = "json", log_level: str = "INFO"):
    """Configure root logger with the specified format.

    Args:
        log_format: "json" or "text"
        log_level: Python log level name
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())

    if log_format == "json":
        try:
            from pythonjsonlogger.json import JsonFormatter

            formatter = JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
                rename_fields={
                    "levelname": "level",
                    "name": "logger",
                    "asctime": "timestamp",
                },
            )
        except ImportError:
            # Fallback if pythonjsonlogger not installed
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
            )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
