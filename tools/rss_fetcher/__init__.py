"""tools.rss_fetcher package.

Fetch + parse RSS 2.0 / Atom 1.0 feeds into a deterministic JSON structure.

Library:
    from tools.rss_fetcher import fetch_feeds, fetch_single_feed, parse_feed_xml
    result = fetch_feeds(["https://example.com/rss"], timeout_seconds=30)
    # result: {"feeds":[...], "errors":[...], "total_entries":N, ...}

CLI:
    python -m tools.rss_fetcher --url https://example.com/rss --output feed.json
    python -m tools.rss_fetcher --urls a,https://b/c --audit inbox/external/audit.jsonl

Network/parse failures are per-feed (logged in `errors`, never raised). Timeout
(max 120s), optional proxy (from cartridges/network_config.json ONLY), audit
JSONL, deterministic output. Pure stdlib. Parsing is network-free and fully
unit-testable via parse_feed_xml(xml_bytes).
"""
from .core import fetch_feeds, fetch_single_feed, write_output, write_audit
from .feed_parser import parse_feed_xml
from .fetcher_schema import FEED_TYPE_RSS, FEED_TYPE_ATOM, make_entry_id

__all__ = ["fetch_feeds", "fetch_single_feed", "parse_feed_xml",
           "write_output", "write_audit", "FEED_TYPE_RSS", "FEED_TYPE_ATOM",
           "make_entry_id"]
