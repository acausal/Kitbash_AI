"""datetime_utils core: parsing, formatting, duration, timezone (stdlib + pytz).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, pytz,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

Design: thin wrapper over datetime + pytz; all functions return JSON-serializable
dicts (constructed via datetime_schema dataclasses). Internal time is UTC;
conversion happens only at boundaries. Output truncated to seconds.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

import pytz

from .datetime_schema import (
    DateTimeComponent,
    DurationResult,
    ParseResult,
    TimezoneOffsetResult,
)

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("datetime_utils")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

_VALID_UNITS = ("seconds", "minutes", "hours", "days", "milliseconds")
_UNIT_SECONDS = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400,
                 "milliseconds": 0.001}


def _utc(dt_aware: datetime) -> datetime:
    return dt_aware.astimezone(pytz.UTC)


def _components(dt_aware: datetime) -> DateTimeComponent:
    u = _utc(dt_aware)
    return DateTimeComponent(u.year, u.month, u.day, u.hour, u.minute, u.second)


def _offset_str(dt_aware: datetime) -> str:
    off = dt_aware.utcoffset()
    if off is None:
        return "+00:00"
    total = int(off.total_seconds())
    sign = "-" if total < 0 else "+"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def _parse_iso_like(s: str, keep_tz: bool = False) -> datetime:
        """Parse an ISO 8601 string (with or without timezone) into an aware dt.

        If keep_tz is True, the datetime keeps its original offset (for capturing
        the input's timezone_offset). Otherwise it is normalized to UTC.
        """
        txt = s.strip()
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {s!r}")
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt if keep_tz else _utc(dt)


def parse_iso8601(timestamp: str) -> dict:
    if not isinstance(timestamp, str):
        raise ValueError("timestamp must be a string")
    dt_in = _parse_iso_like(timestamp, keep_tz=True)   # offset of input as given
    orig_offset = _offset_str(dt_in)
    dt = _utc(dt_in)                                   # normalize to UTC
    res = ParseResult(
        iso8601=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        unix_timestamp=int(dt.timestamp()),
        datetime_components=_components(dt),
        timezone="UTC",
        timezone_offset=orig_offset,
    )
    if _logger:
        _logger.log(event_type="parse_iso8601_complete",
                    data={"input": timestamp, "unix": res.unix_timestamp})
    return res.to_dict()


def parse_epoch(epoch: float, unit: str = "seconds") -> dict:
    if not isinstance(epoch, (int, float)) or isinstance(epoch, bool):
        raise ValueError("epoch must be a number")
    if unit not in ("seconds", "milliseconds"):
        raise ValueError(f"Unrecognized unit: {unit!r} (expected 'seconds'/'milliseconds')")
    if epoch < 0:
        raise ValueError("epoch must be non-negative")
    secs = epoch / 1000.0 if unit == "milliseconds" else float(epoch)
    dt = datetime.fromtimestamp(secs, tz=pytz.UTC)
    res = ParseResult(
        iso8601=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        unix_timestamp=int(dt.timestamp()),
        datetime_components=_components(dt),
        timezone="UTC",
    )
    if _logger:
        _logger.log(event_type="parse_epoch_complete",
                    data={"unix": res.unix_timestamp, "unit": unit})
    return res.to_dict()


def parse_string(date: str, format: str) -> dict:
    if not isinstance(date, str) or not isinstance(format, str):
        raise ValueError("date and format must be strings")
    try:
        naive = datetime.strptime(date, format)
    except ValueError as e:
        raise ValueError(f"date {date!r} does not match format {format!r}: {e}")
    dt = pytz.UTC.localize(naive)
    res = ParseResult(
        iso8601=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        unix_timestamp=int(dt.timestamp()),
        datetime_components=_components(dt),
        timezone="UTC",
    )
    if _logger:
        _logger.log(event_type="parse_string_complete",
                    data={"input": date, "format": format})
    return res.to_dict()


def _detect_and_parse(timestamp_str: str) -> datetime:
    """Parse an ISO 8601 string or a bare Unix epoch (digits)."""
    s = timestamp_str.strip()
    if s.replace(".", "", 1).lstrip("-").isdigit():
        return datetime.fromtimestamp(float(s), tz=pytz.UTC)
    return _parse_iso_like(s)


def format_timestamp(timestamp: str, format: str = "iso8601",
                     timezone: str = "UTC") -> dict:
    if format not in ("iso8601", "unix_seconds", "unix_milliseconds", "human"):
        raise ValueError(f"Unrecognized format: {format!r}")
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone!r}")
    dt = _detect_and_parse(timestamp).astimezone(tz)

    if format == "iso8601":
        value = dt.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0000", "+00:00") \
            if tz != pytz.UTC else dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif format == "unix_seconds":
        value = int(dt.timestamp())
    elif format == "unix_milliseconds":
        value = int(dt.timestamp() * 1000)
    else:  # human
        value = dt.strftime("%Y-%m-%d %H:%M:%S %Z").replace("UTC", "UTC")
    if _logger:
        _logger.log(event_type="format_timestamp_complete",
                    data={"format": format, "timezone": timezone})
    return {
        "original": timestamp,
        "formatted_value": value,
        "format": format,
        "timezone": timezone,
    }


def get_current_time(timezone: str = "UTC") -> dict:
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone!r}")
    dt = datetime.now(tz)
    res = ParseResult(
        iso8601=dt.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0000", "+00:00")
        if tz != pytz.UTC else dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        unix_timestamp=int(dt.timestamp()),
        datetime_components=_components(dt),
        timezone=timezone,
        timezone_offset=_offset_str(dt),
    )
    if _logger:
        _logger.log(event_type="get_current_time_complete", data={"timezone": timezone})
    return res.to_dict()


def duration_between(start: str, end: str, unit: str = "seconds") -> dict:
    if unit not in _VALID_UNITS:
        raise ValueError(f"Unrecognized unit: {unit!r}")
    s = _detect_and_parse(start)
    e = _detect_and_parse(end)
    if e < s:
        raise ValueError("end time must be >= start time")
    delta: timedelta = e - s
    total_seconds = delta.total_seconds()
    factor = _UNIT_SECONDS[unit]
    duration = total_seconds / factor if factor != 0 else total_seconds * 1000
    breakdown = {
        "days": delta.days,
        "hours": delta.seconds // 3600,
        "minutes": (delta.seconds % 3600) // 60,
        "seconds": delta.seconds % 60,
    }
    res = DurationResult(
        start=s.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end=e.strftime("%Y-%m-%dT%H:%M:%SZ"),
        duration=duration,
        unit=unit,
        breakdown=breakdown,
    )
    if _logger:
        _logger.log(event_type="duration_between_complete",
                    data={"duration": duration, "unit": unit})
    return res.to_dict()


def timezone_offset(timezone: str, for_timestamp: Optional[str] = None) -> dict:
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone!r}")
    if for_timestamp:
        dt = _detect_and_parse(for_timestamp).astimezone(tz)
    else:
        dt = datetime.now(tz)
    off = dt.utcoffset()
    offset_seconds = int(off.total_seconds()) if off else 0
    try:
        is_dst = bool(tz.dst(dt.replace(tzinfo=None)))
    except Exception:
        is_dst = False
    res = TimezoneOffsetResult(
        timezone=timezone,
        offset=_offset_str(dt),
        offset_seconds=offset_seconds,
        is_dst=is_dst,
        as_of=dt.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    if _logger:
        _logger.log(event_type="timezone_offset_complete", data={"timezone": timezone})
    return res.to_dict()
