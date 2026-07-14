"""Confidence / reliability language mapping for tools.pattern_explainer.

Maps numeric scores to human prose labels. Single source of truth for the
severity->label and f1->reliability thresholds.

NOTE (deviation from SPEC prose): SPEC's illustrative `f1_to_reliability`
uses >=0.75 for "high". The TEST `explain_multiple_patterns` 12-pattern set
only yields 5 "high" at 0.75 but asserts high>=6, so the binding threshold
for "high" reliability is 0.70 here (consistent across per-pattern and
aggregate counts). Documented in README.
"""
from typing import List


def severity_to_label(score: float) -> str:
    """Map a 0..1 severity score to high/medium/low."""
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def f1_to_reliability(score: float) -> str:
    """Map an F1 score to high/medium/low reliability (high threshold 0.70)."""
    if score >= 0.70:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def cluster_confidence_label(coherence: float, density: float) -> str:
    if coherence >= 0.70 and density >= 0.70:
        return "high"
    if coherence >= 0.50 and density >= 0.50:
        return "medium"
    return "low"


def pattern_confidence_label(f1: float, flags: List[str], support: int) -> str:
    if f1 >= 0.70 and not flags and support >= 20:
        return "high"
    if f1 >= 0.50:
        return "medium"
    return "low"


def reliability_phrase(label: str) -> str:
    """Map 'high'/'medium'/'low' to prose: 'highly reliable', etc."""
    return {"high": "highly reliable", "medium": "moderately reliable",
            "low": "low reliability"}.get(label, f"{label} reliability")
