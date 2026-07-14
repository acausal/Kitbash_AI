"""tools.rss_fetcher network client (stdlib urllib).

Fetches feed XML with timeout, optional proxy (from cartridges/network_config.json
only), no redirect-following in v1 (a 3xx is surfaced as an HTTPError via the
_NoRedirect handler, never silently ingested), User-Agent header. Transport is
injectable for testing without real network. See SPEC-rss_fetcher_v1.md.
"""
import json
import time
import urllib.request
import urllib.error
import urllib.response
import socket

DEFAULT_UA = "Kitbash-RSS-Fetcher/1.0"
MAX_TIMEOUT = 120
MAX_BYTES = 50 * 1024 * 1024  # 50 MB


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """v1 SPEC: do NOT follow 3xx redirects. Surface the redirect as an error
    so the caller logs it (never silently ingests a redirected body)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_proxy(network_config_path: str = None) -> dict:
    """Load proxy ONLY from an explicit config file; never env vars."""
    if not network_config_path:
        return {}
    try:
        with open(network_config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        return {k: cfg[k] for k in ("http_proxy", "https_proxy") if k in cfg}
    except (OSError, ValueError):
        return {}


def default_transport(url: str, timeout: int, user_agent: str, proxy: dict):
    """Real urllib transport. Returns (status_code, body_bytes).

    Redirects are NOT followed (v1 SPEC): a 3xx returns its own status code via
    HTTPError, which fetch_one logs as an HTTPError (not a silent parse)."""
    timeout = min(max(int(timeout), 1), MAX_TIMEOUT)
    handlers = [_NoRedirect()]
    if proxy:
        from urllib.request import ProxyHandler
        handlers.append(ProxyHandler({k: v for k, v in proxy.items()}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError(f"Feed exceeds max size {MAX_BYTES} bytes")
            return resp.getcode(), body
    except urllib.error.HTTPError as e:
        # Includes 3xx when _NoRedirect suppresses the redirect.
        body = e.read(MAX_BYTES + 1)
        return e.code, body
    except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
        raise


def fetch_one(url: str, timeout: int = 30, user_agent: str = DEFAULT_UA,
              proxy: dict = None, transport=None) -> dict:
    """Fetch+parse a single feed. Returns a feed-result dict (never raises)."""
    t0 = time.monotonic()
    transport = transport or default_transport
    try:
        status, body = transport(url, timeout, user_agent, proxy or {})
    except Exception as e:  # network failure (URLError / timeout / ConnectionError)
        return {
            "url": url, "fetch_status": "error", "error": str(e),
            "fetch_time_ms": int((time.monotonic() - t0) * 1000),
        }
    # Non-2xx (3xx redirects, 4xx, 5xx) -> HTTP error; never parsed as feed XML.
    if not (200 <= status < 300):
        return {
            "url": url, "fetch_status": "error", "error": f"HTTP error {status}",
            "error_code": status, "http_status": status,
            "fetch_time_ms": int((time.monotonic() - t0) * 1000),
        }
    try:
        parsed = parse_feed_xml_from_body(body)
    except Exception as e:
        return {
            "url": url, "fetch_status": "error",
            "error": f"parse error: {e}", "http_status": status,
            "fetch_time_ms": int((time.monotonic() - t0) * 1000),
        }
    parsed.update({
        "url": url, "fetch_status": "success", "http_status": status,
        "fetch_timestamp": _now_ios(), "fetch_time_ms": int((time.monotonic() - t0) * 1000),
        "entries_count": len(parsed.get("entries", [])),
    })
    return parsed


def parse_feed_xml_from_body(body: bytes) -> dict:
    # local import avoids a hard dep cycle at module import time
    from .feed_parser import parse_feed_xml
    return parse_feed_xml(body)


def _now_ios() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
