#!/usr/bin/env python3
"""
Google News AF_initDataCallback ds:2 Parser -- Field Index Mapping & Extraction Test

Parses the news_data.json file exported from Google News search results.
The data lives in data_blobs.af_init_data_callbacks where key == "ds:2".

=============================================================================
DS:2 TOP-LEVEL STRUCTURE
=============================================================================
ds:2 = [
    "gsrres",                   # [0] callback identifier (Google Search Results RESponse)
    [ <article_list> ],         # [1] wrapper -- [1][0] is the actual list of 100 entries
    "el mencho"                 # [2] the search query string
]

=============================================================================
ENTRY TYPES (each item in ds:2[1][0])
=============================================================================
There are TWO entry types in the article list:

1. SINGLE ARTICLE ENTRY:
   outer = [article_data, None, None, None, None, None, None, position_index]
   - outer[0] = article data array (51-54 fields)
   - outer[7] = 0-based position index in results

2. CLUSTER/TOPIC ENTRY (multiple articles grouped under one headline):
   outer = [None, cluster_data]
   - outer[0] = None (distinguishes from single)
   - outer[1] = [
       cluster_title,          # [0] str: e.g. "'El Mencho' in Mexico"
       None,                   # [1]
       [sub_article, ...],    # [2] list of sub-articles (same format as single article_data, but 51 fields)
       story_metadata,         # [3] story ID, navigation token
       None,                   # [4]
       result_group_meta,      # [5] result group type info
       position_flag           # [6] int
     ]

=============================================================================
ARTICLE DATA FIELD INDEX MAPPING (article_data array)
=============================================================================
Index  | Type         | Field                    | Notes
-------|-------------|--------------------------|------------------------------------------
[0]    | int         | type_marker              | Always 13
[1]    | list(2)     | article_id               | [1][0]=13, [1][1]=base64 encoded article ID
[2]    | str         | title / headline         | Full article title
[3]    | None/str    | snippet / description    | Always None in this dataset
[4]    | list(1)     | published_timestamp      | [4][0] = Unix epoch seconds (UTC)
[5]    | None        | (unused)                 |
[6]    | str         | article_url              | Direct link to the article (canonical URL)
[7]    | str/None    | article_url_alt          | Sometimes same as [6], sometimes None
[8]    | list(1)     | thumbnail_data           | [8][0] = thumbnail array (see below)
[9]    | None        | (unused)                 |
[10]   | list(4)     | publisher_data           | Publisher/source info (see below)
[11-35]| None        | (unused)                 |
[36]   | list(2)     | publisher_nav_link       | [36][1][0] = ["Go to <Source>", "publications/...", ...]
[37]   | None        | (unused)                 |
[38]   | str         | article_url_canonical    | Same as [6] typically (canonical URL)
[39]   | None        | (unused)                 |
[40]   | str/None    | amp_url                  | AMP version of article URL (if available)
[41]   | None        | (unused)                 |
[42]   | list(1)     | story_metadata           | [42][0] = 29-item array with story/cluster IDs
[43]   | None        | (unused)                 |
[44]   | int         | flag_1                   | Always 1
[45]   | None        | (unused)                 |
[46]   | None        | (unused)                 |
[47]   | list(13)    | flags_array              | Sparse flags, [47][12]=1 for main articles
[48]   | None        | (unused)                 |
[49]   | int         | flag_2                   | Always 1
[50]   | int         | position_in_cluster      | 0-based index within cluster (0 for single)
[51]   | list/None   | authors                  | [[author1], [author2], ...] or None
[52]   | None        | (unused)                 | Only in single articles (not cluster subs)
[53]   | int/None    | has_live_coverage         | 1 = live updates, 0 = normal article

=============================================================================
THUMBNAIL DATA: article_data[8][0]
=============================================================================
Index  | Type   | Field
-------|--------|------------------------------------------
[0]    | str    | Google News proxy path (prefix with https://news.google.com)
[1]    | None   | (unused)
[2]    | int    | width (pixels)
[3]    | int    | height (pixels)
[4]    | None   | (unused)
[5]    | str    | thumbnail hash/ID
[6-12] | None   | (unused)
[13]   | str    | original_image_url (direct source URL)

=============================================================================
PUBLISHER DATA: article_data[10]
=============================================================================
Index  | Type     | Field
-------|----------|------------------------------------------
[0]    | int      | type_marker (always 12)
[1]    | list(2)  | publisher_id: [1][0]=12, [1][1]=base64 encoded ID
[2]    | str      | publisher_name (e.g. "CNN", "Al Jazeera")
[3]    | list     | favicon_data: [3][0]=favicon_url, [3][2]=width, [3][3]=height

=============================================================================
STORY METADATA: article_data[42][0]
=============================================================================
[4]  = str: empty string or result group tag
[6]  = int: 141 (constant)
[10] = int: 37 (constant)
[12] = list(32): sparse, [12][29]=story_id_1, [12][30]=story_id_2, [12][31]=original_image_url
[22] = list(2): [[published_ts], [last_updated_ts, nanoseconds]]
[26] = str: base64 encoded pagination/filter token
[27] = str: base64 encoded token
[28] = int: 0

=============================================================================
OTHER CALLBACK BLOBS
=============================================================================
ds:0 = ["gnmres", [...]]  -- Navigation/topic tabs (India, World, Local, Business, etc.)
ds:1 = ["gsares", [[entity_name, "Topic", entity_metadata, 0]]]
       -- Search entity info. e.g. "Nemesio Oseguera Cervantes" / "Topic"
       -- [2][17] contains entity image/knowledge panel data
"""

import json
import datetime
import sys
from pathlib import Path


def load_news_data(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


def extract_articles(data: dict) -> list[dict]:
    """Extract all articles from ds:2, handling both single and cluster entries."""
    callbacks = data["data_blobs"]["af_init_data_callbacks"]
    ds2 = None
    for cb in callbacks:
        if cb["key"] == "ds:2":
            ds2 = cb["data"]
            break

    if ds2 is None:
        print("ERROR: ds:2 not found in af_init_data_callbacks")
        return []

    search_query = ds2[2] if len(ds2) > 2 else None
    entries = ds2[1][0]

    articles = []
    position = 0

    for outer in entries:
        # --- CLUSTER ENTRY ---
        if outer[0] is None and len(outer) > 1 and outer[1] is not None:
            cluster = outer[1]
            cluster_title = cluster[0]
            sub_articles = cluster[2] if cluster[2] else []

            for sub_idx, sub in enumerate(sub_articles):
                article = _parse_article_data(sub, position, cluster_title=cluster_title, cluster_pos=sub_idx)
                articles.append(article)
                position += 1
            continue

        # --- SINGLE ARTICLE ENTRY ---
        if outer[0] is not None and isinstance(outer[0], list):
            article_data = outer[0]
            article = _parse_article_data(article_data, position)
            articles.append(article)
            position += 1

    return articles


def _parse_article_data(entry: list, position: int, cluster_title: str | None = None, cluster_pos: int | None = None) -> dict:
    """Parse a single article data array into a clean dict."""

    # Title
    title = entry[2] if len(entry) > 2 else None

    # URL (prefer [6], fallback to [38])
    url = None
    if len(entry) > 6 and entry[6]:
        url = entry[6]
    elif len(entry) > 38 and entry[38]:
        url = entry[38]

    # AMP URL
    amp_url = entry[40] if len(entry) > 40 and entry[40] else None

    # Timestamp
    timestamp = None
    published_date = None
    if len(entry) > 4 and entry[4] and isinstance(entry[4], list) and entry[4][0]:
        timestamp = entry[4][0]
        published_date = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Publisher
    publisher_name = None
    favicon_url = None
    if len(entry) > 10 and entry[10] and isinstance(entry[10], list):
        pub = entry[10]
        publisher_name = pub[2] if len(pub) > 2 else None
        if len(pub) > 3 and pub[3] and isinstance(pub[3], list) and pub[3][0]:
            favicon_url = pub[3][0]

    # Thumbnail
    thumbnail_url = None
    thumbnail_original_url = None
    thumbnail_width = None
    thumbnail_height = None
    if len(entry) > 8 and entry[8] and isinstance(entry[8], list) and entry[8][0]:
        thumb = entry[8][0]
        if thumb[0]:
            thumbnail_url = f"https://news.google.com{thumb[0]}"
        thumbnail_width = thumb[2] if len(thumb) > 2 else None
        thumbnail_height = thumb[3] if len(thumb) > 3 else None
        thumbnail_original_url = thumb[13] if len(thumb) > 13 else None

    # Article ID (base64 encoded)
    article_id = None
    if len(entry) > 1 and entry[1] and isinstance(entry[1], list) and len(entry[1]) > 1:
        article_id = entry[1][1]

    # Authors
    authors = []
    if len(entry) > 51 and entry[51] and isinstance(entry[51], list):
        for author_group in entry[51]:
            if isinstance(author_group, list):
                for name in author_group:
                    if isinstance(name, str):
                        authors.append(name)

    # Publisher navigation link
    publisher_nav = None
    if len(entry) > 36 and entry[36] and isinstance(entry[36], list):
        nav_data = entry[36]
        if len(nav_data) > 1 and nav_data[1] and isinstance(nav_data[1], list) and nav_data[1][0]:
            publisher_nav = nav_data[1][0][1] if len(nav_data[1][0]) > 1 else None

    # Story metadata
    story_ids = {}
    last_updated = None
    if len(entry) > 42 and entry[42] and isinstance(entry[42], list) and entry[42][0]:
        meta = entry[42][0]
        # Story IDs from [12]
        if len(meta) > 12 and meta[12] and isinstance(meta[12], list):
            ids = meta[12]
            if len(ids) > 29 and ids[29]:
                story_ids["id_1"] = ids[29]
            if len(ids) > 30 and ids[30]:
                story_ids["id_2"] = ids[30]
        # Last updated timestamp from [22]
        if len(meta) > 22 and meta[22] and isinstance(meta[22], list) and len(meta[22]) > 1:
            if meta[22][1] and isinstance(meta[22][1], list) and meta[22][1][0]:
                last_updated = datetime.datetime.fromtimestamp(
                    meta[22][1][0], tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC")

    # Has live coverage flag
    has_live_coverage = False
    if len(entry) > 53 and entry[53] == 1:
        has_live_coverage = True

    # Position in cluster
    position_in_cluster = entry[50] if len(entry) > 50 else 0

    return {
        "position": position,
        "title": title,
        "url": url,
        "amp_url": amp_url,
        "article_id": article_id,
        "published_timestamp": timestamp,
        "published_date": published_date,
        "last_updated": last_updated,
        "publisher_name": publisher_name,
        "favicon_url": favicon_url,
        "thumbnail_url": thumbnail_url,
        "thumbnail_original_url": thumbnail_original_url,
        "thumbnail_width": thumbnail_width,
        "thumbnail_height": thumbnail_height,
        "authors": authors if authors else None,
        "publisher_nav_path": publisher_nav,
        "story_ids": story_ids if story_ids else None,
        "has_live_coverage": has_live_coverage,
        "cluster_title": cluster_title,
        "cluster_position": cluster_pos,
        "position_in_cluster": position_in_cluster,
    }


def print_table(articles: list[dict]) -> None:
    """Print a clean formatted table of articles."""

    # Header
    print(f"{'#':>3}  {'Title':<70}  {'Source':<22}  {'Date':>16}  {'Authors':<25}  URL")
    print("-" * 210)

    for a in articles:
        pos = a["position"]
        title = (a["title"] or "N/A")[:68]
        if len(a["title"] or "") > 68:
            title += ".."
        source = (a["publisher_name"] or "N/A")[:22]
        date = a["published_date"][:16] if a["published_date"] else "N/A"
        url = (a["url"] or "N/A")[:80]
        authors = ", ".join(a["authors"]) if a["authors"] else ""
        authors = authors[:25]
        cluster_marker = ""
        if a["cluster_title"]:
            cluster_marker = f" [CLUSTER: {a['cluster_title'][:20]}]"

        print(f"{pos:>3}  {title:<70}  {source:<22}  {date:>16}  {authors:<25}  {url}{cluster_marker}")


def print_summary(articles: list[dict], data: dict) -> None:
    """Print summary statistics."""

    callbacks = data["data_blobs"]["af_init_data_callbacks"]

    # ds:1 entity info
    ds1 = None
    for cb in callbacks:
        if cb["key"] == "ds:1":
            ds1 = cb["data"]
            break

    ds2 = [cb["data"] for cb in callbacks if cb["key"] == "ds:2"][0]

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"Search query:        {ds2[2]}")
    if ds1:
        entity = ds1[1][0]
        print(f"Search entity:       {entity[0]} ({entity[1]})")

    print(f"Total entries in ds:2[1][0]: {len(ds2[1][0])}")

    # Count types
    singles = sum(1 for a in articles if a["cluster_title"] is None)
    clustered = sum(1 for a in articles if a["cluster_title"] is not None)
    cluster_groups = set()
    for a in articles:
        if a["cluster_title"]:
            cluster_groups.add(a["cluster_title"])

    print(f"Single articles:     {singles}")
    print(f"Cluster groups:      {len(cluster_groups)}")
    print(f"Clustered articles:  {clustered}")
    print(f"Total articles:      {len(articles)}")

    # Source distribution (top 15)
    sources = {}
    for a in articles:
        src = a["publisher_name"] or "Unknown"
        sources[src] = sources.get(src, 0) + 1

    print(f"\nTop 15 sources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1])[:15]:
        print(f"  {src:<30} {count:>3} articles")

    # Articles with authors
    with_authors = sum(1 for a in articles if a["authors"])
    print(f"\nArticles with authors: {with_authors}/{len(articles)}")

    # Articles with AMP URLs
    with_amp = sum(1 for a in articles if a["amp_url"])
    print(f"Articles with AMP URL: {with_amp}/{len(articles)}")

    # Articles with live coverage
    live = sum(1 for a in articles if a["has_live_coverage"])
    print(f"Articles with live coverage flag: {live}/{len(articles)}")

    # Date range
    timestamps = [a["published_timestamp"] for a in articles if a["published_timestamp"]]
    if timestamps:
        earliest = datetime.datetime.fromtimestamp(min(timestamps), tz=datetime.timezone.utc)
        latest = datetime.datetime.fromtimestamp(max(timestamps), tz=datetime.timezone.utc)
        print(f"\nDate range: {earliest.strftime('%Y-%m-%d %H:%M UTC')} -> {latest.strftime('%Y-%m-%d %H:%M UTC')}")

    # Callback keys
    print(f"\nAll AF_initDataCallback keys:")
    for cb in callbacks:
        key = cb["key"]
        d = cb["data"]
        if isinstance(d, list):
            print(f"  {key}: identifier={d[0]!r}, payload_items={len(d)}")
        else:
            print(f"  {key}: type={type(d).__name__}")


def main():
    filepath = Path(__file__).parent / "news_data.json"
    if not filepath.exists():
        print(f"ERROR: {filepath} not found")
        sys.exit(1)

    print(f"Loading {filepath}...")
    data = load_news_data(str(filepath))

    print("Extracting articles from ds:2...")
    articles = extract_articles(data)

    if not articles:
        print("No articles found!")
        sys.exit(1)

    print(f"\nExtracted {len(articles)} articles.\n")
    print_table(articles)
    print_summary(articles, data)

    # Print first article as full JSON example
    print("\n" + "=" * 80)
    print("FULL PARSED ARTICLE EXAMPLE (first article)")
    print("=" * 80)
    print(json.dumps(articles[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
