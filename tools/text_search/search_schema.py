"""Dataclasses for tools.text_search (see SPEC-text_search_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ContextLine:
    line_number: int
    text: str


@dataclass
class MatchPosition:
    start: int  # character offset in line (0-indexed)
    end: int


@dataclass
class Match:
    match_number: int
    line_number: int
    matched_text: str
    match_position: MatchPosition
    context_before: List[ContextLine] = field(default_factory=list)
    context_after: List[ContextLine] = field(default_factory=list)


@dataclass
class SearchResults:
    total_matches: int
    total_lines_with_matches: int
    matches: List[Match]


@dataclass
class SearchReport:
    search_params: Dict[str, Any]
    results: SearchResults


@dataclass
class ExtractedGroup:
    match_number: int
    line_number: int
    full_match: str
    extracted_groups: Dict[str, str]  # group_0, group_1, ...


@dataclass
class CountReport:
    pattern: str
    case_insensitive: bool
    total_matches: int
    total_lines_searched: int
    lines_with_matches: int
    match_density: float


@dataclass
class ReplaceChange:
    change_number: int
    line_number: int
    original: str
    replaced: str


@dataclass
class ReplaceReport:
    search_params: Dict[str, Any]
    original_text: str
    modified_text: str
    changes: List[ReplaceChange]
