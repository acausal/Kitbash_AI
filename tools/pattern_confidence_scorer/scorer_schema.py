"""Dataclasses for tools.pattern_confidence_scorer (see SPEC-pattern_confidence_scorer_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Metrics:
    precision: float
    recall: float
    f1_score: float
    true_positive_rate: float
    false_positive_rate: float
    specificity: float
    support: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "true_positive_rate": self.true_positive_rate,
            "false_positive_rate": self.false_positive_rate,
            "specificity": self.specificity,
            "support": self.support,
        }


@dataclass
class ConfusionDetails:
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    total_observations: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "total_observations": self.total_observations,
        }


@dataclass
class Interpretation:
    reliability: str
    confidence_flag: str
    sample_size_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"reliability": self.reliability, "confidence_flag": self.confidence_flag}
        if self.sample_size_note is not None:
            d["sample_size_note"] = self.sample_size_note
        return d


@dataclass
class PatternScore:
    pattern_id: str
    pattern: List[str]
    pattern_frequency_in_data: int
    metrics: Metrics
    interpretation: Interpretation
    details: ConfusionDetails

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern": self.pattern,
            "pattern_frequency_in_data": self.pattern_frequency_in_data,
            "metrics": self.metrics.to_dict(),
            "interpretation": self.interpretation.to_dict(),
            "details": self.details.to_dict(),
        }


@dataclass
class AggregateStatistics:
    mean_precision: float
    mean_recall: float
    mean_f1: float
    patterns_with_high_confidence: int
    patterns_with_low_sample_size: int
    patterns_with_low_reliability: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean_precision": self.mean_precision,
            "mean_recall": self.mean_recall,
            "mean_f1": self.mean_f1,
            "patterns_with_high_confidence": self.patterns_with_high_confidence,
            "patterns_with_low_sample_size": self.patterns_with_low_sample_size,
            "patterns_with_low_reliability": self.patterns_with_low_reliability,
        }
