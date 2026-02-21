from pydantic import BaseModel, field_validator

from app.schemas.scrape import _normalize_url


class MapRequest(BaseModel):
    url: str

    @field_validator("url", mode="before")
    @classmethod
    def _add_protocol(cls, v: str) -> str:
        return _normalize_url(v)
    search: str | None = None
    limit: int = 100
    include_subdomains: bool = True
    use_sitemap: bool = True


class LinkResult(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    lastmod: str | None = None
    priority: float | None = None


class MapResponse(BaseModel):
    success: bool
    total: int
    links: list[LinkResult]
    error: str | None = None
    job_id: str | None = None
