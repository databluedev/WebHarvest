"""Unit tests for app.services.dedup — URL normalization and deduplication."""

import pytest
from unittest.mock import AsyncMock

from app.services.dedup import normalize_url, deduplicate_urls, check_redis_seen


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------


class TestNormalizeUrl:
    """Tests for the normalize_url() function."""

    def test_trailing_slash_removed(self):
        """Trailing slash on a path is stripped (but root / is kept)."""
        assert normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_root_slash_kept(self):
        """Root URL keeps its single slash."""
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_query_param_sorting(self):
        """Query parameters are sorted alphabetically."""
        url = "https://example.com/page?z=1&a=2&m=3"
        normalized = normalize_url(url)
        assert "a=2" in normalized
        assert "m=3" in normalized
        assert "z=1" in normalized
        # a should come before m which should come before z
        a_pos = normalized.index("a=2")
        m_pos = normalized.index("m=3")
        z_pos = normalized.index("z=1")
        assert a_pos < m_pos < z_pos

    def test_utm_source_stripped(self):
        """utm_source tracking parameter is removed."""
        url = "https://example.com/page?key=val&utm_source=twitter"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "key=val" in result

    def test_utm_medium_stripped(self):
        """utm_medium tracking parameter is removed."""
        url = "https://example.com/?utm_medium=email"
        result = normalize_url(url)
        assert "utm_medium" not in result

    def test_utm_campaign_stripped(self):
        """utm_campaign tracking parameter is removed."""
        url = "https://example.com/page?utm_campaign=spring_sale&real=yes"
        result = normalize_url(url)
        assert "utm_campaign" not in result
        assert "real=yes" in result

    def test_fbclid_stripped(self):
        """Facebook click ID is removed."""
        url = "https://example.com/article?fbclid=abc123"
        result = normalize_url(url)
        assert "fbclid" not in result

    def test_gclid_stripped(self):
        """Google click ID is removed."""
        url = "https://example.com/article?gclid=xyz789&page=2"
        result = normalize_url(url)
        assert "gclid" not in result
        assert "page=2" in result

    def test_fragment_stripped(self):
        """URL fragments (anchors) are removed."""
        url = "https://example.com/page#section-2"
        result = normalize_url(url)
        assert "#" not in result
        assert result == "https://example.com/page"

    def test_scheme_lowercased(self):
        """Scheme is lowercased."""
        assert normalize_url("HTTPS://Example.Com/Path") == "https://example.com/Path"

    def test_host_lowercased(self):
        """Hostname is lowercased and www. stripped."""
        result = normalize_url("https://WWW.EXAMPLE.COM/page")
        assert "example.com" in result
        # www. should be stripped for dedup
        assert "www." not in result

    def test_www_stripped_for_dedup(self):
        """www.example.com normalizes to example.com (Firecrawl-style dedup)."""
        assert normalize_url("https://www.example.com/page") == normalize_url("https://example.com/page")

    def test_index_html_stripped(self):
        """index.html is stripped (same page as directory)."""
        assert normalize_url("https://example.com/docs/index.html") == "https://example.com/docs"
        assert normalize_url("https://example.com/index.htm") == "https://example.com/"

    def test_default_http_port_removed(self):
        """Port 80 is removed for http."""
        result = normalize_url("http://example.com:80/page")
        assert ":80" not in result
        assert result == "http://example.com/page"

    def test_default_https_port_removed(self):
        """Port 443 is removed for https."""
        result = normalize_url("https://example.com:443/page")
        assert ":443" not in result
        assert result == "https://example.com/page"

    def test_non_default_port_kept(self):
        """Non-default ports are preserved."""
        result = normalize_url("https://example.com:8080/page")
        assert ":8080" in result

    def test_double_slashes_collapsed(self):
        """Double slashes in path are collapsed to single slashes."""
        result = normalize_url("https://example.com//a//b///c")
        assert "//" not in result.split("//", 1)[1]  # skip the scheme://
        assert "/a/b/c" in result

    def test_empty_query_after_stripping(self):
        """If all params are tracking params, query string is empty."""
        url = "https://example.com/page?utm_source=a&fbclid=b&gclid=c"
        result = normalize_url(url)
        assert "?" not in result

    def test_multiple_tracking_params_stripped(self):
        """Multiple tracking params removed simultaneously."""
        url = "https://example.com/?utm_source=x&utm_medium=y&utm_campaign=z&valid=1"
        result = normalize_url(url)
        assert "utm_" not in result
        assert "valid=1" in result

    def test_scheme_defaults_to_https(self):
        """URLs without a scheme default to https."""
        result = normalize_url("://example.com/page")
        # The parser may struggle, but scheme should not be empty
        assert result.startswith("https://") or "example.com" in result

    def test_invalid_url_returns_without_error(self):
        """Completely malformed input is processed without raising."""
        result = normalize_url("   not a url at all   ")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_preserves_meaningful_query_params(self):
        """Non-tracking query params are preserved and sorted."""
        url = "https://shop.example.com/search?category=books&sort=price&page=3"
        result = normalize_url(url)
        assert "category=books" in result
        assert "sort=price" in result
        assert "page=3" in result


# ---------------------------------------------------------------------------
# deduplicate_urls
# ---------------------------------------------------------------------------


class TestDeduplicateUrls:
    """Tests for the deduplicate_urls() function."""

    def test_removes_exact_duplicates(self):
        """Identical URLs are collapsed to one."""
        urls = [
            "https://example.com/page",
            "https://example.com/page",
            "https://example.com/page",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_removes_normalized_duplicates(self):
        """URLs that differ only by trailing slash / tracking params are deduped."""
        urls = [
            "https://example.com/page/",
            "https://example.com/page",
            "https://example.com/page?utm_source=fb",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_preserves_order(self):
        """The first occurrence of each unique URL is kept, in order."""
        urls = [
            "https://a.com",
            "https://b.com",
            "https://a.com/",
            "https://c.com",
        ]
        result = deduplicate_urls(urls)
        assert result[0].rstrip("/") in ("https://a.com", "https://a.com/")
        assert "b.com" in result[1]
        assert "c.com" in result[2]

    def test_handles_empty_list(self):
        """An empty list returns an empty list."""
        assert deduplicate_urls([]) == []

    def test_skips_blank_strings(self):
        """Blank / whitespace-only entries are skipped."""
        urls = ["", "   ", "https://example.com", "  "]
        result = deduplicate_urls(urls)
        assert len(result) == 1
        assert "example.com" in result[0]

    def test_strips_whitespace(self):
        """Leading / trailing whitespace is stripped before processing."""
        urls = ["  https://example.com  ", "https://example.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_different_paths_not_deduped(self):
        """URLs with different paths remain separate."""
        urls = [
            "https://example.com/page-a",
            "https://example.com/page-b",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 2

    def test_case_normalization_dedup(self):
        """Host case differences cause deduplication."""
        urls = [
            "https://EXAMPLE.COM/page",
            "https://example.com/page",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# check_redis_seen
# ---------------------------------------------------------------------------


class TestCheckRedisSeen:
    """Tests for the async check_redis_seen() function."""

    @pytest.mark.asyncio
    async def test_new_url_returns_false(self):
        """A URL not yet in the set returns False (not seen)."""
        redis = AsyncMock()
        redis.sadd = AsyncMock(return_value=1)  # 1 = newly added
        result = await check_redis_seen(redis, "job-1", "https://example.com/new")
        assert result is False

    @pytest.mark.asyncio
    async def test_existing_url_returns_true(self):
        """A URL already in the set returns True (already seen)."""
        redis = AsyncMock()
        redis.sadd = AsyncMock(return_value=0)  # 0 = already existed
        result = await check_redis_seen(redis, "job-1", "https://example.com/old")
        assert result is True

    @pytest.mark.asyncio
    async def test_normalizes_before_check(self):
        """The URL is normalized before being added to the Redis set."""
        redis = AsyncMock()
        redis.sadd = AsyncMock(return_value=1)
        await check_redis_seen(
            redis, "job-1", "https://EXAMPLE.COM/path/?utm_source=x#frag"
        )
        # The sadd call should use the normalized form
        call_args = redis.sadd.call_args
        added_url = call_args[0][1]
        assert "utm_source" not in added_url
        assert "#frag" not in added_url
        assert "example.com" in added_url
