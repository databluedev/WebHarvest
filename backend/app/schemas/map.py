from pydantic import BaseModel


class MapRequest(BaseModel):
    url: str
    search: str | None = None
    limit: int = 100
    include_subdomains: bool = True
    use_sitemap: bool = True


class LinkResult(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None


class MapResponse(BaseModel):
    success: bool
    total: int
    links: list[LinkResult]
    error: str | None = None
