"""Dataclasses for tools.multispectral_analyzer (see SPEC-multispectral_analyzer_v1.md).

Stdlib-only (dataclasses). MVP = 7 text spectra (classification/markov/anomaly deferred).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SpectrumResult:
    tool_id: str
    success: bool
    output: Optional[dict] = None
    error: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class DivergenceFlag:
    divergence_type: str
    spectra_involved: List[str]
    description: str
    severity: str  # "info" | "warning" | "critical"


@dataclass
class MultispectralResult:
    request_id: str
    input_summary: Dict[str, object]
    spectral_results: Dict[str, SpectrumResult]
    fingerprint: Dict[str, object]
    divergence_flags: List[DivergenceFlag]
    spectrum_config: Dict[str, object]
    execution_summary: Dict[str, object]
