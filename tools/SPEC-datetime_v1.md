# SPEC: DateTime Utilities v1

**Module:** `tools/datetime_utils/`  
**Status:** Ready for build  
**Dependencies:** stdlib `datetime`, `pytz` (PyPI)  
**Priority:** High (foundational data plumbing; unblocks time-series operations and log parsing)

---

## Overview

A POSIX-inspired datetime utility tool for parsing, formatting, duration calculations, and timezone handling. Exposes core datetime operations as atomic CLI commands and composable functions.

**Design principle:** Thin wrapper over stdlib `datetime` + `pytz`; no date arithmetic sugar (e.g., no "next Tuesday"). Suitable for both tool composition and direct scripting.

---

## Scope

### In Scope ✓
- Parse ISO 8601 timestamps (RFC 3339 with/without timezone)
- Parse common formats: Unix epoch (seconds, milliseconds), human-readable strings (specified via format string)
- Format timestamps to ISO 8601, Unix epoch, human-readable strings
- Calculate duration between two timestamps (days, hours, minutes, seconds)
- Get current time in UTC or specified timezone
- Timezone conversion: parse string in one timezone, output in another
- Timezone offset queries (e.g., "What is UTC offset for America/Denver?")
- Output: JSON with all results

### Out of Scope ✗
- Natural language time parsing ("next Tuesday", "in 2 weeks") — deferred to v2
- Cron syntax parsing
- Calendar operations (business days, holidays)
- i18n date formatting
- Millisecond/microsecond precision (truncate to seconds in output)
- Leap second handling

---

## Module Structure

```
tools/datetime_utils/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  datetime_schema.py             # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, floats, dicts).

#### 1. `parse_iso8601(timestamp_str: str) -> dict`
**Purpose:** Parse ISO 8601 / RFC 3339 timestamp.

**Input:**
- `timestamp_str` (str): ISO 8601 string, e.g., `"2026-07-14T12:30:45Z"` or `"2026-07-14T12:30:45+02:00"`

**Output (JSON):**
```json
{
  "iso8601": "2026-07-14T12:30:45+00:00",
  "unix_timestamp": 1752495045,
  "datetime_components": {
    "year": 2026,
    "month": 7,
    "day": 14,
    "hour": 12,
    "minute": 30,
    "second": 45
  },
  "timezone": "UTC",
  "timezone_offset": "+00:00"
}
```

**Error handling:**
- `ValueError` if string is not valid ISO 8601

---

#### 2. `parse_epoch(epoch_value: float, unit: str = "seconds") -> dict`
**Purpose:** Parse Unix epoch to datetime.

**Input:**
- `epoch_value` (float): Unix timestamp
- `unit` (str): One of `"seconds"`, `"milliseconds"` (default: `"seconds"`)

**Output (JSON):**
```json
{
  "iso8601": "2026-07-14T12:30:45+00:00",
  "unix_timestamp": 1752495045,
  "datetime_components": {
    "year": 2026,
    "month": 7,
    "day": 14,
    "hour": 12,
    "minute": 30,
    "second": 45
  },
  "timezone": "UTC"
}
```

**Error handling:**
- `ValueError` if epoch_value is negative or unit is unrecognized

---

#### 3. `parse_string(date_str: str, format_str: str) -> dict`
**Purpose:** Parse custom-formatted date string using strptime format string.

**Input:**
- `date_str` (str): Date string, e.g., `"July 14, 2026 12:30 PM"`
- `format_str` (str): strptime format, e.g., `"%B %d, %Y %I:%M %p"`

**Output (JSON):**
```json
{
  "iso8601": "2026-07-14T12:30:00+00:00",
  "unix_timestamp": 1752495000,
  "datetime_components": {
    "year": 2026,
    "month": 7,
    "day": 14,
    "hour": 12,
    "minute": 30,
    "second": 0
  },
  "timezone": "UTC"
}
```

**Error handling:**
- `ValueError` if date_str doesn't match format_str

---

#### 4. `format_timestamp(timestamp_str: str, output_format: str = "iso8601", timezone: str = "UTC") -> dict`
**Purpose:** Format a parsed timestamp to different formats.

**Input:**
- `timestamp_str` (str): ISO 8601 string or Unix epoch (auto-detected)
- `output_format` (str): One of `"iso8601"`, `"unix_seconds"`, `"unix_milliseconds"`, `"human"` (default: `"iso8601"`)
- `timezone` (str): Target timezone (default: `"UTC"`)

**Output (JSON):**
```json
{
  "original": "2026-07-14T12:30:45Z",
  "formatted_value": "2026-07-14T12:30:45-06:00",
  "format": "iso8601",
  "timezone": "America/Denver"
}
```

**Supported output formats:**
- `"iso8601"` → ISO 8601 string with timezone
- `"unix_seconds"` → Unix epoch as integer
- `"unix_milliseconds"` → Unix epoch in milliseconds (as integer)
- `"human"` → `"2026-07-14 12:30:45 UTC"` (ISO-like but human-readable)

**Error handling:**
- `ValueError` if output_format is unrecognized or timezone is invalid

---

#### 5. `get_current_time(timezone: str = "UTC") -> dict`
**Purpose:** Get current time in specified timezone.

**Input:**
- `timezone` (str): Timezone name, e.g., `"America/Denver"`, `"UTC"` (default: `"UTC"`)

**Output (JSON):**
```json
{
  "iso8601": "2026-07-14T18:30:45-06:00",
  "unix_timestamp": 1752495045,
  "datetime_components": {
    "year": 2026,
    "month": 7,
    "day": 14,
    "hour": 18,
    "minute": 30,
    "second": 45
  },
  "timezone": "America/Denver",
  "timezone_offset": "-06:00"
}
```

**Error handling:**
- `ValueError` if timezone is invalid

---

#### 6. `duration_between(start_str: str, end_str: str, unit: str = "seconds") -> dict`
**Purpose:** Calculate duration between two timestamps.

**Input:**
- `start_str` (str): ISO 8601 or Unix epoch (start time)
- `end_str` (str): ISO 8601 or Unix epoch (end time)
- `unit` (str): One of `"seconds"`, `"minutes"`, `"hours"`, `"days"` (default: `"seconds"`)

**Output (JSON):**
```json
{
  "start": "2026-07-14T12:30:45Z",
  "end": "2026-07-14T14:30:45Z",
  "duration": 7200,
  "unit": "seconds",
  "breakdown": {
    "days": 0,
    "hours": 2,
    "minutes": 0,
    "seconds": 0
  }
}
```

**Error handling:**
- `ValueError` if timestamps are invalid or end < start

---

#### 7. `timezone_offset(timezone: str, for_timestamp: str = None) -> dict`
**Purpose:** Get UTC offset for timezone at specific time (or now).

**Input:**
- `timezone` (str): Timezone name, e.g., `"America/Denver"`
- `for_timestamp` (str, optional): ISO 8601 string; if not provided, use current time

**Output (JSON):**
```json
{
  "timezone": "America/Denver",
  "offset": "-06:00",
  "offset_seconds": -21600,
  "is_dst": true,
  "as_of": "2026-07-14T18:30:45"
}
```

**Error handling:**
- `ValueError` if timezone is invalid

---

### CLI Interface (in `cli.py`)

All commands read input from stdin (JSON) or CLI arguments; output to stdout (JSON).

```bash
# Parse ISO 8601
echo '{"timestamp": "2026-07-14T12:30:45Z"}' | python -m tools.datetime_utils parse_iso8601

# Parse Unix epoch
echo '{"epoch": 1752495045, "unit": "seconds"}' | python -m tools.datetime_utils parse_epoch

# Parse custom format
echo '{"date": "July 14, 2026 12:30 PM", "format": "%B %d, %Y %I:%M %p"}' \
  | python -m tools.datetime_utils parse_string

# Format timestamp
echo '{"timestamp": "2026-07-14T12:30:45Z", "format": "unix_seconds"}' \
  | python -m tools.datetime_utils format_timestamp

# Get current time in timezone
echo '{"timezone": "America/Denver"}' | python -m tools.datetime_utils get_current_time

# Calculate duration
echo '{"start": "2026-07-14T12:30:45Z", "end": "2026-07-14T14:30:45Z", "unit": "seconds"}' \
  | python -m tools.datetime_utils duration_between

# Get timezone offset
echo '{"timezone": "America/Denver"}' | python -m tools.datetime_utils timezone_offset
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `datetime_schema.py`)

```python
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class DateTimeComponent:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int

@dataclass
class ParseResult:
    iso8601: str
    unix_timestamp: int
    datetime_components: DateTimeComponent
    timezone: str
    timezone_offset: Optional[str] = None

@dataclass
class DurationResult:
    start: str
    end: str
    duration: float  # in requested unit
    unit: str
    breakdown: Dict[str, int]  # days, hours, minutes, seconds

@dataclass
class TimezoneOffsetResult:
    timezone: str
    offset: str  # e.g., "-06:00"
    offset_seconds: int
    is_dst: bool
    as_of: str
```

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable (no file I/O)
- `ValueError` — invalid input format, unrecognized timezone, invalid format string, negative/invalid epoch
- `RuntimeError` — internal parsing/conversion failure (should be rare)
- `IOError` — not applicable (no file I/O)

**Logging:**
- Use `structured_logger.get_event_logger("datetime_utils")`
- Log events: `parse_iso8601_started`, `parse_iso8601_complete`, `parse_iso8601_failed`
- Metadata: input string, unit, output timezone, error details if applicable

---

## Test Cases

### Happy Path
1. Parse ISO 8601: `"2026-07-14T12:30:45Z"` → correct components
2. Parse ISO 8601 with offset: `"2026-07-14T12:30:45-06:00"` → normalized to UTC + original offset captured
3. Parse Unix epoch (seconds): `1752495045` → correct ISO 8601
4. Parse Unix epoch (milliseconds): `1752495045000` → correct ISO 8601
5. Parse custom format: `"July 14, 2026"` with format `"%B %d, %Y"` → correct components
6. Format to Unix seconds: ISO 8601 → integer timestamp
7. Calculate duration: 2 hours → 7200 seconds, breakdown correct
8. Get current time (UTC): returns valid ISO 8601
9. Get current time (Denver): returns correct offset + timezone name
10. Timezone offset (no DST): UTC → `"+00:00"`, offset_seconds `0`
11. Timezone offset (DST active): Denver in July → `"-06:00"` (Mountain Daylight Time)

### Edge Cases
12. Epoch `0` (Unix epoch start): `1970-01-01T00:00:00Z`
13. Leap year date: `"2024-02-29"` parses correctly
14. Midnight: `"2026-07-14T00:00:00Z"` → hour 0, minute 0, second 0
15. Duration between same timestamp: → 0 with breakdown all zeros
16. Format to human-readable: produces readable string

### Error Cases
17. Invalid ISO 8601: `"not-a-date"` → `ValueError`
18. Invalid format string: `"2026-07-14"` with format `"%Y-%m-%d %H:%M"` → `ValueError`
19. Unrecognized timezone: `"America/NotReal"` → `ValueError`
20. Negative epoch: `-1` → `ValueError`
21. End time before start time: `duration_between("2026-07-14T14:30:45Z", "2026-07-14T12:30:45Z")` → `ValueError`
22. Invalid output format: `format_timestamp(..., output_format="invalid")` → `ValueError`

### CLI Behavior
23. CLI exit code 0 on success, 1 on ValueError, 2 on RuntimeError
24. CLI with invalid JSON input → `ValueError` (JSON parsing fails)
25. CLI reads from stdin and writes to stdout as JSON

---

## Non-Goals (Explicitly Out of Scope)

- Natural language parsing ("next Tuesday", relative dates)
- Cron expression parsing or scheduling
- Calendar math (business days, holidays, day-of-week arithmetic)
- Internationalization or locale-specific formatting
- Leap second handling
- Precision beyond seconds (microseconds/nanoseconds)
- Fuzzy date matching or OCR-based date extraction

---

## Implementation Notes

### Timezone Handling
- Use `pytz` for timezone database (always use `.localize()` and `.normalize()` for DST safety)
- Store all internal datetimes as UTC; convert only at boundaries (parse input, format output)
- Reject ambiguous datetime transitions (e.g., DST fold) with clear error messages

### Epoch Parsing
- Assume Unix epoch; Python `datetime.fromtimestamp()` handles both seconds and milliseconds
- Truncate to seconds (discard sub-second precision in output)

### Format String Compatibility
- Use Python's `strptime` format codes (`%Y`, `%m`, `%d`, etc.)
- Document common patterns in README (ISO 8601, RFC 2822, etc.)

### Composability
- All functions return JSON-serializable dicts (not dataclass instances) for tool composition
- Use consistent key names across functions (`iso8601`, `unix_timestamp`, `timezone`, `offset`)

---

## Dependencies

```
pytz          # Timezone database and conversions
stdlib datetime # datetime, timedelta, timezone
stdlib json    # JSON serialization
structured_logger  # Kitbash logging
```

Lightweight; no heavy data science libraries.

---

## Success Criteria

- ✅ All 25 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ JSON output validated against schema (fields present, types correct)
- ✅ Timezone handling uses `pytz.localize()`/`normalize()` (DST safety)
- ✅ No external API calls (all local stdlib + pytz)
- ✅ Errors logged via structured_logger
- ✅ README documents all functions, format codes, and common patterns

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
