# datetime_utils

POSIX-inspired datetime utilities (v1). Part of the input-sieve / document-
preprocessing "data plumbing" layer: parse, format, duration, and timezone
operations over stdlib `datetime` + `pytz`. Thin wrapper — no calendar math,
no natural-language parsing (v2+). Isolation-first tool (stdlib + pytz +
optional `structured_logger`).

## Library

```python
from tools.datetime_utils import (
    parse_iso8601, parse_epoch, parse_string, format_timestamp,
    get_current_time, duration_between, timezone_offset,
)
parse_iso8601("2026-07-14T12:30:45Z")        # -> dict with iso8601/unix/components
parse_epoch(1752495045, unit="seconds")
parse_string("July 14, 2026 12:30 PM", "%B %d, %Y %I:%M %p")
format_timestamp("2026-07-14T12:30:45Z", "unix_seconds", "America/Denver")
get_current_time("America/Denver")
duration_between("2026-07-14T12:30:45Z", "2026-07-14T14:30:45Z", "seconds")
timezone_offset("America/Denver", "2026-07-14T12:30:45Z")
```

Every function returns a **plain JSON-serializable dict** (constructed from
`datetime_schema` dataclasses) so output composes with other tools. Internal
time is UTC; conversion happens only at input/output boundaries. Output is
truncated to seconds.

## CLI

Multi-command; reads a JSON object from **stdin**, writes JSON to **stdout**:

```bash
echo '{"timestamp": "2026-07-14T12:30:45Z"}' | python -m tools.datetime_utils parse_iso8601
echo '{"epoch": 1752495045, "unit": "seconds"}' | python -m tools.datetime_utils parse_epoch
echo '{"date": "July 14, 2026 12:30 PM", "format": "%B %d, %Y %I:%M %p"}' | python -m tools.datetime_utils parse_string
echo '{"timestamp": "2026-07-14T12:30:45Z", "format": "unix_seconds"}' | python -m tools.datetime_utils format_timestamp
echo '{"timezone": "America/Denver"}' | python -m tools.datetime_utils get_current_time
echo '{"start": "2026-07-14T12:30:45Z", "end": "2026-07-14T14:30:45Z", "unit": "seconds"}' | python -m tools.datetime_utils duration_between
echo '{"timezone": "America/Denver"}' | python -m tools.datetime_utils timezone_offset
```

**Exit codes:** `0` success · `1` invalid input (`ValueError`/bad JSON) · `2` internal error.

## Requirements

- `pytz` (PyPI). Install in the Kitbash `.venv`: `uv pip install pytz`.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.datetime_utils ...`
