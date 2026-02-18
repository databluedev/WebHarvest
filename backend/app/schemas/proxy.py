from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class ProxyCreateRequest(BaseModel):
    proxy_url: str  # e.g. http://user:pass@host:port or socks5://host:port
    proxy_type: str = "http"  # http, https, socks5
    label: str | None = None


class ProxyBulkCreateRequest(BaseModel):
    proxies: list[str]  # List of proxy URLs, one per item
    proxy_type: str = "http"


class ProxyResponse(BaseModel):
    id: UUID
    proxy_url_masked: str  # Masked URL for display
    proxy_type: str
    label: str | None
    is_active: bool
    created_at: datetime


class ProxyListResponse(BaseModel):
    proxies: list[ProxyResponse]
    total: int
