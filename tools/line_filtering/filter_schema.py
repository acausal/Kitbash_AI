"""Dataclasses for tools.line_filtering (see SPEC-line_filtering_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FrequencyEntry:
    line: str
    count: int
    frequency_percent: float


@dataclass
class DistributionStats:
    most_common: str
    most_common_count: int
    least_common: str
    least_common_count: int


@dataclass
class SortResult:
    sorted_lines: List[str]
    line_count: int


@dataclass
class DeduplicateResult:
    deduplicated_lines: List[str]
    unique_line_count: int
    duplicates_removed: int


@dataclass
class FrequencyResult:
    frequency_list: List[FrequencyEntry]
    distribution_stats: DistributionStats


@dataclass
class FilterByFrequencyResult:
    filtered_lines: List[str]
    lines_kept: int
    lines_removed: int
    unique_lines_kept: int


@dataclass
class UniqueResult:
    lines_appearing_once: List[str]
    count: int


@dataclass
class HeadTailResult:
    extracted_lines: List[str]
    count: int
