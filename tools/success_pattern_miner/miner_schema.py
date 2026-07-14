"""Dataclasses for tools.success_pattern_miner (see SPEC-success_pattern_miner_v1.md).

These mirror the JSON shapes. Core functions build plain dicts (per the SPEC's
composability requirement); dataclasses document the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Pattern:
    pattern_id: str
    pattern_type: str
    sequence: List[Any]            # tool names (str) or grain ids (int)
    frequency: int
    support: float
    coverage: float
    confidence_estimate: float
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    grain_sequence: Optional[List[Any]] = None  # only for mixed patterns


@dataclass
class RunResult:
    discovery_run_id: str
    timestamp: str
    input_traces_count: int
    success_traces_count: int
    patterns: List[Pattern]
    metadata: Dict[str, Any]
