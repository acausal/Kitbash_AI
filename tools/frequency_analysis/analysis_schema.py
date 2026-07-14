"""Dataclasses for tools.frequency_analysis (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class FrequencyEntry:
    token: str
    frequency: int
    rank: int
    percentile: float
    coverage_percent: float


@dataclass
class CorpusFrequencyEntry:
    token: str
    total_frequency: int
    document_frequency: int
    avg_frequency_per_doc: float
    rank: int
    percentile: float
