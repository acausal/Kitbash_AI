"""Dataclasses for tools.log_parser (see SPEC-log_parser_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ChainStep:
    position: int
    element_id: Any  # fact_id / grain_id / explicit element_id
    element_type: str  # "fact" or "grain"
    traversal_type: str
    cartridge: Optional[str] = None
    timestamp: Optional[str] = None
    weight: Optional[float] = None


@dataclass
class Trace:
    trace_id: str
    query_id: str
    chain_type: str  # "intra_query", "inter_query", etc.
    chain: List[Dict[str, Any]]
    session_id: Optional[str] = None
    timestamp: str = field(default_factory=_now_iso)
    chain_length: int = field(init=False)
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.chain_length = len(self.chain)


@dataclass
class ParseReport:
    total_lines: int
    valid_traces: int
    invalid_lines: int
    errors: List[Dict[str, Any]]  # line_number, error, line_content


@dataclass
class FilterReport:
    filter_criteria: Dict[str, Any]
    total_traces_input: int
    traces_after_filtering: int
    filtered_out: int


@dataclass
class AggregatedChainStats:
    total_traces: int
    unique_chain_sequences: int
    sequence_frequency: List[Dict[str, Any]]
    sequence_type_distribution: Dict[str, int]


@dataclass
class TransitionStats:
    total_traces: int
    total_steps_extracted: int
    unique_step_types: int
    step_frequency: List[Dict[str, Any]]
    transition_type_distribution: Dict[str, int]
