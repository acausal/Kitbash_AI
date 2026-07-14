"""Dataclasses mirroring the Anomaly Scorer JSON output shapes.

Pure documentation of the contract; the core functions build plain dicts for
composability (same style as tools.pattern_confidence_scorer).
"""""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SeverityFactors:
    magnitude_ratio: float = 0.0
    above_std_deviations: float = 0.0
    recency_weight: float = 1.0
    sample_size_confidence: float = 1.0


@dataclass
class Anomaly:
    anomaly_id: str
    anomaly_type: str
    severity: float = 0.0
    severity_factors: Dict[str, Any] = field(default_factory=dict)
    possible_causes: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recommendation: str = ""
    note: str = ""


@dataclass
class AggregateStatistics:
    total_analyzed: int = 0
    with_anomalies: int = 0
    mean_severity: float = 0.0
    high_severity_count: int = 0
