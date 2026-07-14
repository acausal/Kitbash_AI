# SPEC: RSS Fetcher v1

**Module:** `tools/rss_fetcher/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, urllib, xml.etree.ElementTree, datetime)  
**Priority:** Medium (external ingestion; feeds into validation pipeline)

---

## Overview

Fetch RSS/Atom feeds from configurable URLs and emit raw feed data to `inbox/external/` for downstream validation and processing. Simple, deterministic, local-first ingestion with explicit consent-gating for network access and optional feed filtering.

**Design principle:** Minimal tool, deterministic output. Fetch feed, parse XML, emit JSON. No deduplication, no filtering, no smart logic—that's downstream. Fail-loud on network errors. Respect timeout and resource limits.

**Use case:** "Fetch my RSS feeds and write them to inbox/external/ so I can validate and process them."

---

## Scope

### In Scope ✓
- Fetch RSS 2.0 and Atom 1.0 feeds from HTTP(S) URLs
- Parse feed XML; extract entries (items)
- Emit JSON array of feed entries to stdout/file
- Support multiple feeds in batch (list of URLs)
- Filesystem safety: write ONLY to `inbox/external/` (Filesystem Access v1)
- Network safety: respect timeout (30s default, configurable), no redirects followed, fail-loud on errors
- Proxy support: read from `cartridges/network_config.json` if configured (optional)
- User approval logging: emit audit trail entry to `inbox/external/audit.jsonl`
- Feed metadata: include feed title, description, fetch timestamp
- Rate-limiting: optional delay between fetches (respect server politeness)

### Out of Scope ✗
- Deduplication (downstream tool)
- Filtering by date, topic, or keyword (downstream validator)
- Parsing non-RSS/Atom formats (JSON feeds, etc.)
- Content extraction beyond title/link/description/pubDate
- Feed validation (that's Structured Input Validator)
- Persistent feed state or differential fetching (always full fetch)
- Interactive UI or manual feed management

---

## Module Structure

```
tools/rss_fetcher/
  __init__.py                     # exports main functions
  core.py                         # fetching and parsing logic
  feed_parser.py                  # RSS 2.0 + Atom 1.0 parsing
  network.py                      # HTTP client with timeout and proxy support
  cli.py                          # argparse CLI
  fetcher_schema.py               # dataclasses for feed items and output
  README.md                         # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types.

#### 1. `fetch_feeds(feed_urls: list, timeout_seconds: int = 30, delay_between_fetches_seconds: float = 0.5, user_agent: str = None) -> dict`

**Purpose:** Fetch one or more RSS/Atom feeds and parse entries.

**Input:**
- `feed_urls` (list): URLs to fetch:
  ```json
  [
    "https://example.com/rss",
    "https://example.org/feed.xml"
  ]
  ```

- `timeout_seconds` (int): HTTP request timeout (default: 30)
- `delay_between_fetches_seconds` (float): Sleep between fetches to avoid hammering server (default: 0.5)
- `user_agent` (str): Custom User-Agent header (default: `Kitbash-RSS-Fetcher/1.0`)

**Output:**
```json
{
  "fetch_run_id": "rss_fetch_001",
  "timestamp": "2026-07-14T14:50:00Z",
  "feeds_requested": 2,
  "feeds_fetched": 2,
  "feeds_failed": 0,
  "total_entries": 87,
  "feeds": [
    {
      "url": "https://example.com/rss",
      "feed_type": "rss_2.0",
      "title": "Example Feed",
      "description": "A sample RSS feed",
      "link": "https://example.com",
      "language": "en",
      "fetch_timestamp": "2026-07-14T14:50:00Z",
      "fetch_status": "success",
      "http_status": 200,
      "fetch_time_ms": 234,
      "entries_count": 45,
      "entries": [
        {
          "entry_id": "item_001",
          "title": "Article Title",
          "link": "https://example.com/article/1",
          "description": "Article summary or full content",
          "pub_date": "2026-07-14T10:30:00Z",
          "author": "author@example.com",
          "categories": ["tech", "news"],
          "guid": "https://example.com/article/1"
        },
        {
          "entry_id": "item_002",
          "title": "Another Article",
          "link": "https://example.com/article/2",
          "description": "...",
          "pub_date": "2026-07-14T08:15:00Z",
          "author": null,
          "categories": [],
          "guid": "https://example.com/article/2"
        }
      ]
    },
    {
      "url": "https://example.org/feed.xml",
      "feed_type": "atom_1.0",
      "title": "Example Atom Feed",
      "description": null,
      "link": "https://example.org",
      "language": null,
      "fetch_timestamp": "2026-07-14T14:50:01Z",
      "fetch_status": "success",
      "http_status": 200,
      "fetch_time_ms": 156,
      "entries_count": 42,
      "entries": [...]
    }
  ],
  "errors": []
}
```

#### 2. `fetch_single_feed(feed_url: str, timeout_seconds: int = 30) -> dict`

**Purpose:** Fetch a single feed (simpler interface).

**Input:**
- `feed_url` (str): Single URL
- `timeout_seconds` (int): HTTP timeout

**Output:** Single feed object (same structure as above, but just one feed in list)

---

## Feed Entry Schema

Each entry includes:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `entry_id` | string | Yes | Unique ID (generated from guid or title+pubdate hash) |
| `title` | string | No | Entry title (empty string if missing) |
| `link` | string | No | Link to entry (empty string if missing) |
| `description` | string | No | Summary or full content (empty string if missing) |
| `pub_date` | string (ISO 8601) | No | Publication date (null if unparseable) |
| `author` | string | No | Author email or name (null if missing) |
| `categories` | array of strings | No | Category tags (empty array if none) |
| `guid` | string | No | Globally unique ID from RSS (null if missing) |

---

## Error Handling

### Network Errors
- **HTTP 404/403/410:** Log to errors array, continue with next feed
- **Timeout:** Log to errors array, continue
- **Connection refused:** Log to errors array, continue
- **Invalid URL:** ValueError, exit 1

### Parse Errors
- **Malformed XML:** Log to errors array, skip entry or entire feed (fail-loud)
- **Missing required fields (title/link):** Emit entry with available fields; use defaults for missing

### Output
```json
{
  "errors": [
    {
      "url": "https://dead.example.com/rss",
      "error_type": "HTTPError",
      "error_code": 404,
      "error_message": "Not Found",
      "timestamp": "2026-07-14T14:50:00Z"
    },
    {
      "url": "https://bad.example.com/rss",
      "error_type": "Timeout",
      "error_message": "Request timed out after 30 seconds",
      "timestamp": "2026-07-14T14:50:01Z"
    }
  ]
}
```

---

## Filesystem & Network Safety

### Filesystem (REQUIRED - use Filesystem Access v1)
- **Write location:** `inbox/external/rss_feeds_{timestamp}.json` (never workspace/)
- **No exceptions:** Filesystem Access validator enforces this; tool fails if attempt to write elsewhere

### Network
- **No proxy inheritance:** Disable environment proxy by default (urllib doesn't follow proxies unless explicitly configured)
- **Optional proxy support:** If `cartridges/network_config.json` exists:
  ```json
  {
    "http_proxy": "http://proxy.example.com:8080",
    "https_proxy": "https://proxy.example.com:8080"
  }
  ```
  Then use those (and ONLY those); don't fall back to environment variables
- **Timeout:** Enforce 30-second timeout (configurable, max 120s)
- **No redirects:** Don't follow HTTP redirects (follow_redirects=False)
- **User-Agent:** Identify as Kitbash-RSS-Fetcher/1.0

### Audit Logging
- Emit entry to `inbox/external/audit.jsonl`:
  ```json
  {
    "timestamp": "2026-07-14T14:50:00Z",
    "event": "rss_fetch",
    "tool": "rss_fetcher",
    "url": "https://example.com/rss",
    "status": "success",
    "http_status": 200,
    "entries_fetched": 45,
    "fetch_time_ms": 234
  }
  ```

---

## CLI Interface

```bash
# Fetch single feed
python -m tools.rss_fetcher \
  --url https://example.com/rss \
  --output /path/to/inbox/external/feed.json

# Fetch multiple feeds
python -m tools.rss_fetcher \
  --urls https://example.com/rss,https://example.org/feed.xml \
  --output /path/to/inbox/external/feeds.json

# Fetch with custom timeout and delay
python -m tools.rss_fetcher \
  --url https://example.com/rss \
  --timeout 60 \
  --delay 1.0 \
  --output feed.json

# Read feeds from file (one URL per line)
python -m tools.rss_fetcher \
  --urls-file my_feeds.txt \
  --output feeds.json

# Fetch and write to stdout (for piping)
python -m tools.rss_fetcher \
  --url https://example.com/rss
```

---

## Input/Output Formats

### Input
- `feed_urls` or `--url`/`--urls` (comma-separated or file)
- HTTP(S) URLs only; fail on non-URLs

### Output
- JSON object with `feeds` array and `errors` array
- Deterministic output: same feed URL → same structure (modulo entry order)

---

## Implementation Notes

1. **XML parsing:** Use `xml.etree.ElementTree` (stdlib); handle namespaces for Atom feeds
2. **Feed type detection:** Check root element (rss → RSS 2.0; feed → Atom 1.0)
3. **Entry extraction:** 
   - RSS 2.0: iterate `<item>` elements
   - Atom 1.0: iterate `<entry>` elements
4. **Date parsing:** Try ISO 8601 first; fall back to RFC 2822 (email date format); if both fail, set to null
5. **Entry ID generation:** Use `<guid>` (RSS) or `<id>` (Atom) if present; else hash `title + pub_date`
6. **Timeout enforcement:** Use `urllib.request.urlopen()` with timeout parameter
7. **Error handling:** Catch URLError, HTTPError, Timeout, socket.timeout; log and continue
8. **Audit logging:** Use `structured_logger.get_event_logger("rss_fetcher")`
9. **Delay implementation:** `time.sleep(delay_between_fetches_seconds)` between fetches

---

## Error Semantics

- Exit 0: Success (≥1 feed fetched successfully)
- Exit 1: ValueError (invalid URLs, missing required arguments)
- Exit 2: RuntimeError (I/O error writing to output file, file permission denied)

Note: Network errors on individual feeds do NOT cause exit 1/2; they're logged in `errors` array.

---

## Testing Strategy

### Explicit Test Cases (in `TEST-rss_fetcher_examples.json`)

1. **Valid RSS feed:** Fetch real RSS 2.0 feed → parse correctly, emit 45+ entries
2. **Valid Atom feed:** Fetch real Atom 1.0 feed → parse correctly
3. **Multiple feeds:** Fetch 3 URLs → all succeed, entries aggregated correctly
4. **Network error (404):** One feed returns 404 → logged to errors array, other feeds still fetched
5. **Malformed XML:** Feed has invalid XML → logged to errors, parsing stops for that feed
6. **Empty feed:** Feed with 0 entries → success, empty entries array
7. **Timeout:** Slow server (simulate with delay) → times out after 30s, logged to errors
8. **No proxy inheritance:** Ensure environment HTTP_PROXY is ignored (unless cartridges/network_config.json is set)

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, urllib.request, urllib.error, xml.etree.ElementTree, datetime, time, socket, hashlib
- **External libs:** None (stdlib only)
- **Resource limits:**
  - Max feed size: 50 MB (fail if larger)
  - Max timeout: 120 seconds
  - Max concurrent fetches: 1 (sequential only; v1)
- **Hardware:** CPU-only; network I/O bound

---

## Related Tools

- **Filesystem Access v1:** Enforces write-to-inbox/external-only
- **Structured Input Validator v1:** Validates fetched feed JSON against schema
- **File Operations:** Downstream tools read from inbox/external/

---

## Non-Goals

- **Deduplication:** RSS Fetcher doesn't deduplicate entries across feeds or time
- **Filtering:** No built-in filtering by date, topic, or keyword (Validator or downstream tool handles this)
- **Caching/differential fetch:** Always full fetch; no persistent state
- **Feed subscription management:** Doesn't track which feeds to fetch; that's orchestration layer
- **Parallel fetching:** Sequential only (v1); v2 can add parallelism if needed
- **JSON Feed format:** RSS 2.0 and Atom 1.0 only

---

## Post-1.0 Extensions

1. **Parallel fetching:** Async/threading support for fetching multiple feeds concurrently
2. **Differential fetching:** Track last-fetched timestamp; only fetch new entries since last run
3. **Feed validation:** Built-in Lark grammar validation (currently Structured Input Validator does this)
4. **Content extraction:** Extract full article text from feed entries (requires additional libs; deferred)
5. **Feed pooling:** Support feed discovery (e.g., follow feed URL redirects to find feed list)

---

**Last updated:** 2026-07-14  
**For:** Kitbash external ingestion pipeline  
**Related:** TOOL_PHILOSOPHY.md, TOOLS_SAFETY_ARCHITECTURE.md, Structured Input Validator v1, Filesystem Access v1
