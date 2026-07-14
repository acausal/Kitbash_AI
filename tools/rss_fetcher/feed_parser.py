"""tools.rss_fetcher feed parsing (stdlib only).

Parses RSS 2.0 and Atom 1.0 XML into the SPEC feed-entry structure. Pure
function of XML bytes -> dict; no network, no I/O. See SPEC-rss_fetcher_v1.md.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .fetcher_schema import FEED_TYPE_RSS, FEED_TYPE_ATOM, make_entry_id, now_iso

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_date(s: str):
    """ISO 8601 first; fall back to RFC 2822; else None."""
    if not s:
        return None
    s = s.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        pass
    try:
        dt = parsedate_to_datetime(s)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError, IndexError):
        return None


def parse_feed_xml(xml_bytes: bytes) -> dict:
    """Parse RSS/Atom XML into a feed dict (no fetch; raises on malformed XML)."""
    root = ET.fromstring(xml_bytes)
    raw = root.tag  # namespace-sensitive; do NOT lowercase (Atom NS is case-exact)
    if raw == "rss":
        parsed = _parse_rss(root)
    elif raw == f"{_ATOM_NS}feed" or raw == "feed":
        parsed = _parse_atom(root)
    else:
        raise ValueError(f"Unrecognized feed root element: {raw}")
    parsed["entries_count"] = len(parsed.get("entries", []))
    return parsed


def _parse_rss(root) -> dict:
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS feed missing <channel>")
    entries = []
    for item in channel.findall("item"):
        guid_el = item.find("guid")
        guid = _text(guid_el) or None
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        desc = _text(item.find("description")) or _text(item.find("content:encoded"))
        pub = _parse_date(_text(item.find("pubDate")))
        author = _text(item.find("author")) or None
        cats = [c.text.strip() for c in item.findall("category") if (c.text or "").strip()]
        entries.append({
            "entry_id": make_entry_id(guid, title, pub),
            "title": title, "link": link, "description": desc,
            "pub_date": pub, "author": author, "categories": cats, "guid": guid,
        })
    return {
        "feed_type": FEED_TYPE_RSS,
        "title": _text(channel.find("title")),
        "description": _text(channel.find("description")) or None,
        "link": _text(channel.find("link")) or None,
        "language": _text(channel.find("language")) or None,
        "entries": entries,
    }


def _parse_atom(root) -> dict:
    entries = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        id_el = entry.find(f"{_ATOM_NS}id")
        guid = _text(id_el) or None
        title_el = entry.find(f"{_ATOM_NS}title")
        title = _text(title_el)
        link = ""
        for l in entry.findall(f"{_ATOM_NS}link"):
            rel = l.get("rel")
            if rel is None or rel == "alternate":
                link = l.get("href") or ""
                break
        desc_el = entry.find(f"{_ATOM_NS}summary")
        if desc_el is None:
            desc_el = entry.find(f"{_ATOM_NS}content")
        desc = _text(desc_el)
        pub = _parse_date(_text(entry.find(f"{_ATOM_NS}updated")) or _text(entry.find(f"{_ATOM_NS}published")))
        author_el = entry.find(f"{_ATOM_NS}author")
        author = _text(author_el.find(f"{_ATOM_NS}name")) if author_el is not None else None
        cats = [c.get("term") for c in entry.findall(f"{_ATOM_NS}category") if c.get("term")]
        entries.append({
            "entry_id": make_entry_id(guid, title, pub),
            "title": title, "link": link, "description": desc,
            "pub_date": pub, "author": author, "categories": cats, "guid": guid,
        })
    return {
        "feed_type": FEED_TYPE_ATOM,
        "title": _text(root.find(f"{_ATOM_NS}title")),
        "description": _text(root.find(f"{_ATOM_NS}subtitle")) or None,
        "link": (root.find(f"{_ATOM_NS}link").get("href") if root.find(f"{_ATOM_NS}link") is not None else None),
        "language": None,
        "entries": entries,
    }
