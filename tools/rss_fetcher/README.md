# rss_fetcher

Fetch + parse RSS 2.0 / Atom 1.0 feeds into a deterministic JSON structure for
downstream validation. `tools.rss_fetcher`.

## Interface

```python
from tools.rss_fetcher import fetch_feeds, parse_feed_xml
result = fetch_feeds(["https://example.com/rss"], timeout_seconds=30)
# {"fetch_run_id":..., "feeds_requested":1, "feeds_fetched":1, "feeds_failed":0,
#  "total_entries":N, "feeds":[{...entry...}], "errors":[]}
```

| Function | Purpose |
|----------|---------|
| `fetch_feeds(urls, timeout_seconds=30, delay_between_fetches_seconds=0.5, user_agent=None)` | Fetch+parse many feeds |
| `fetch_single_feed(url, timeout_seconds=30)` | Single feed |
| `parse_feed_xml(xml_bytes)` | Parse RSS/Atom XML → feed dict (no network) |

**Entry fields:** `entry_id` (guid or hash), `title`, `link`, `description`,
`pub_date` (ISO), `author`, `categories`, `guid`. Feed failures are per-feed —
logged in `errors`, never raised. Timeout (max 120s), optional proxy (from
`cartridges/network_config.json` ONLY), audit JSONL, sequential fetches.

## CLI

```bash
python -m tools.rss_fetcher --url https://example.com/rss --output feed.json
python -m tools.rss_fetcher --urls a,https://b/c --audit inbox/external/audit.jsonl
```

Exit 0 = ≥1 feed fetched; 1 = invalid args / none fetched; 2 = I/O error.
Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-rss_fetcher_v1.md` · **Test:** `TEST-rss_fetcher_examples.json`
