"""Table extraction from HTML — detects data tables and extracts structured data."""

import logging
import re

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def _is_data_table(table: Tag) -> tuple[bool, int]:
    """Score a table to determine if it's a data table (not layout).

    Returns (is_data_table, score).
    """
    score = 0
    # Has thead/tbody
    if table.find("thead"):
        score += 2
    if table.find("tbody"):
        score += 1
    # Has th elements
    ths = table.find_all("th")
    if ths:
        score += 2
    # Has caption or summary
    if table.find("caption"):
        score += 2
    if table.get("summary"):
        score += 1
    # Consistent column count
    rows = table.find_all("tr")
    if len(rows) >= 2:
        col_counts = []
        for row in rows[:10]:  # Check first 10 rows
            cells = row.find_all(["td", "th"])
            col_counts.append(len(cells))
        if col_counts and len(set(col_counts)) <= 2:
            score += 2
    # Nested tables → likely layout
    if table.find("table"):
        score -= 3
    # Role presentation → layout
    role = (table.get("role") or "").lower()
    if role in ("presentation", "none"):
        score -= 3
    # Minimum rows for data
    if len(rows) >= 3:
        score += 1

    return score >= 3, score


def _expand_colspan(cells: list[Tag]) -> list[str]:
    """Expand cells with colspan into repeated values."""
    expanded = []
    for cell in cells:
        text = cell.get_text(strip=True)
        colspan = int(cell.get("colspan", 1) or 1)
        expanded.extend([text] * colspan)
    return expanded


def extract_tables(html: str) -> list[dict]:
    """Extract structured data from HTML tables.

    Returns a list of table dicts with:
    - headers: list[str]
    - rows: list[list[str]]
    - metadata: {row_count, column_count, has_headers, caption}
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for table in soup.find_all("table"):
        is_data, score = _is_data_table(table)
        if not is_data:
            continue

        headers = []
        rows = []
        caption = ""

        # Extract caption
        cap_tag = table.find("caption")
        if cap_tag:
            caption = cap_tag.get_text(strip=True)

        # Extract headers
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = _expand_colspan(header_row.find_all(["th", "td"]))
        elif not headers:
            # Check first row for th elements
            first_row = table.find("tr")
            if first_row:
                ths = first_row.find_all("th")
                if ths:
                    headers = _expand_colspan(ths)

        # Extract body rows
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            row_data = _expand_colspan(cells)
            # Skip if this is the header row we already extracted
            if headers and row_data == headers:
                continue
            rows.append(row_data)

        if not rows:
            continue

        # Generate default headers if none found
        if not headers:
            max_cols = max(len(r) for r in rows) if rows else 0
            headers = [f"Column {i+1}" for i in range(max_cols)]

        results.append({
            "headers": headers,
            "rows": rows,
            "metadata": {
                "row_count": len(rows),
                "column_count": len(headers),
                "has_headers": bool(thead or table.find("th")),
                "caption": caption,
                "score": score,
            },
        })

    return results
