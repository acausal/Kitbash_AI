"""Dataclasses mirroring tools.pattern_explainer JSON output (documentation)."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Explanation:
    explanation_type: str
    one_liner: str
    summary: str
    detailed_explanation: str
    confidence: str
    confidence_justification: str
    implications: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CollisionExplanation(Explanation):
    cluster_id: str = ""


@dataclass
class AnomalyExplanation(Explanation):
    anomaly_id: str = ""
    severity_label: str = ""
    severity: float = 0.0


@dataclass
class PatternReliabilityExplanation(Explanation):
    pattern_id: str = ""
    reliability_level: str = ""
    reliability_breakdown: Dict[str, str] = field(default_factory=dict)
    confidence_flags: List[str] = field(default_factory=list)
    sample_size_assessment: str = ""
    use_cases: List[str] = field(default_factory=list)
    comparison_to_baseline: str = ""


@dataclass
class PatternCollectionBrief:
    summary_type: str
    total_patterns: int
    high_reliability_patterns: int
    medium_reliability_patterns: int
    low_reliability_patterns: int
    aggregate_summary: str
    pattern_summaries: List[Dict[str, Any]] = field(default_factory=list)
    top_patterns_by_reliability: List[Dict[str, Any]] = field(default_factory=list)
    patterns_needing_attention: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
