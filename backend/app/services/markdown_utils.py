"""Markdown post-processing — citations, fit markdown, network capture."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MarkdownResult:
    """Enhanced markdown output with citations and filtered content."""
    raw_markdown: str = ""
    markdown_with_citations: str = ""
    references_markdown: str = ""
    fit_markdown: str | None = None
    fit_html: str | None = None


def generate_citations(markdown: str) -> MarkdownResult:
    """Convert inline links to numbered citations.

    [text](url) → text⟨1⟩
    References section appended at bottom.
    """
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    references: list[tuple[str, str]] = []
    url_to_ref: dict[str, int] = {}

    def _replace_link(match: re.Match) -> str:
        text = match.group(1)
        url = match.group(2)
        if url not in url_to_ref:
            url_to_ref[url] = len(references) + 1
            references.append((url, text))
        ref_num = url_to_ref[url]
        return f"{text}⟨{ref_num}⟩"

    cited = link_pattern.sub(_replace_link, markdown)

    # Build references section
    ref_lines = []
    for i, (url, text) in enumerate(references, 1):
        ref_lines.append(f"⟨{i}⟩ {url} — {text}")

    references_md = "\n".join(ref_lines)

    result = MarkdownResult(
        raw_markdown=markdown,
        markdown_with_citations=cited,
        references_markdown=references_md,
    )
    return result


def generate_fit_markdown(
    markdown: str,
    html: str,
    filter_type: str = "pruning",
    query: str | None = None,
) -> MarkdownResult:
    """Generate filtered 'fit' markdown using content filtering.

    Args:
        markdown: Raw markdown.
        html: Original HTML for filtering.
        filter_type: "bm25" or "pruning".
        query: Optional query for BM25 relevance.

    Returns:
        MarkdownResult with fit_markdown populated.
    """
    from app.services.content_filter import BM25ContentFilter, PruningContentFilter
    from app.services.content import html_to_markdown

    result = generate_citations(markdown)

    if filter_type == "bm25":
        content_filter = BM25ContentFilter()
    else:
        content_filter = PruningContentFilter()

    filtered_html = content_filter.filter_content(html, query=query)
    result.fit_html = filtered_html

    try:
        result.fit_markdown = html_to_markdown(filtered_html)
    except Exception:
        result.fit_markdown = markdown

    return result
