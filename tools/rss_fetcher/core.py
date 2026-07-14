"""tools.rss_fetcher core (stdlib only).

Orchestrates fetching one or many feeds: builds the SPEC run-result dict with
feeds + errors arrays, optional delay between fetches, optional audit logging
and output writing. Network/parse failures are per-feed (logged, not raised).
See SPEC-rss_fetcher_v1.md.
"""
import time
import json
from datetime import datetime, timezone

from .fetcher_schema import now_iso
from .network import fetch_one, load_proxy, DEFAULT_UA

DEFAULT_DELAY = 0.5


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_feeds(feed_urls: list, timeout_seconds: int = 30,
                delay_between_fetches_seconds: float = DEFAULT_DELAY,
                user_agent: str = DEFAULT_UA, proxy: dict = None,
                transport=None) -> dict:
    """Fetch and parse many feeds. Returns the SPEC run-result dict."""
    feeds = []
    errors = []
    for i, url in enumerate(feed_urls):
        if i > 0 and delay_between_fetches_seconds:
            time.sleep(delay_between_fetches_seconds)
        res = fetch_one(url, timeout_seconds, user_agent, proxy, transport=transport)
        if res.get("fetch_status") == "error":
            errors.append({
                "url": url,
                "error_type": _classify(res.get("error", "")),
                "error_code": res.get("error_code"),
                "error_message": res.get("error", ""),
                "timestamp": _now(),
            })
        else:
            feeds.append(res)
    return {
        "fetch_run_id": f"rss_fetch_{_now().replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')}",
        "timestamp": _now(),
        "feeds_requested": len(feed_urls),
        "feeds_fetched": len(feeds),
        "feeds_failed": len(errors),
        "total_entries": sum(f.get("entries_count", 0) for f in feeds),
        "feeds": feeds,
        "errors": errors,
    }


def fetch_single_feed(feed_url: str, timeout_seconds: int = 30,
                      user_agent: str = DEFAULT_UA, proxy: dict = None,
                      transport=None) -> dict:
    """Fetch a single feed; returns the run-result dict (one feed in `feeds`)."""
    return fetch_feeds([feed_url], timeout_seconds, delay_between_fetches_seconds=0,
                        user_agent=user_agent, proxy=proxy, transport=transport)


def write_output(result: dict, output_path: str) -> None:
    """Write the run-result JSON to `output_path` (direct stdlib write)."""
    import os
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def write_audit(result: dict, audit_path: str) -> None:
    """Append one audit line per fetched feed to `audit_path` (JSONL)."""
    import os
    parent = os.path.dirname(audit_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lines = []
    for f in result.get("feeds", []):
        lines.append(json.dumps({
            "timestamp": f.get("fetch_timestamp", _now()),
            "event": "rss_fetch", "tool": "rss_fetcher", "url": f.get("url"),
            "status": f.get("fetch_status"), "http_status": f.get("http_status"),
            "entries_fetched": f.get("entries_count", 0),
            "fetch_time_ms": f.get("fetch_time_ms"),
        }))
    if lines:
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def _classify(msg: str) -> str:
    m = msg.lower()
    if "timed out" in m or "timeout" in m:
        return "Timeout"
    if "http error" in m:
        return "HTTPError"
    if "urlopen" in m or "getaddrinfo" in m or "connection" in m:
        return "ConnectionError"
    if "parse error" in m:
        return "ParseError"
    return "Error"
