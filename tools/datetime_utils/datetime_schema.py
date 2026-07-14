"""Dataclasses for tools.datetime_utils (see SPEC-datetime_v1.md).

These mirror the JSON output shapes. Core functions construct them and return
to_dict() so callers get plain JSON-serializable dicts (per the SPEC's
composability requirement).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass
class DateTimeComponent:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParseResult:
    iso8601: str
    unix_timestamp: int
    datetime_components: DateTimeComponent
    timezone: str
    timezone_offset: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["datetime_components"] = self.datetime_components.to_dict()
        return d


@dataclass
class DurationResult:
    start: str
    end: str
    duration: float       # in requested unit
    unit: str
    breakdown: Dict[str, int]   # days, hours, minutes, seconds

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimezoneOffsetResult:
    timezone: str
    offset: str          # e.g. "-06:00"
    offset_seconds: int
    is_dst: bool
    as_of: str

    def to_dict(self) -> dict:
        return asdict(self)
