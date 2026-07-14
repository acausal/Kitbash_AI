"""tools.rss_fetcher schema helpers (stdlib only).

Pure helpers shared by the RSS/Atom fetcher: timestamp formatting, entry-id
generation, feed-type constants. See SPEC-rss_fetcher_v1.md.
"""
from datetime import datetime, timezone
import hashlib

FEED_TYPE_RSS = "rss_2.0"
FEED_TYPE_ATOM = "atom_1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_entry_id(guid: str = None, title: str = "", pub_date: str = None) -> str:
    """Stable entry id: guid if present, else hash(title + pub_date)."""
    if guid:
        return guid
    h = hashlib.sha1(f"{title}|{pub_date}".encode("utf-8")).hexdigest()[:16]
    return f"entry_{h}"
