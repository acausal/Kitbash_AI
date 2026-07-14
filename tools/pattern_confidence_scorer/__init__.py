"""tools.pattern_confidence_scorer package.

Library:
    from tools.pattern_confidence_scorer import (
        score_patterns_against_traces, score_patterns_against_dream_bucket,
        compare_pattern_reliability, decay_confidence_by_age,
    )
"""
from .core import (
    score_patterns_against_traces, score_patterns_against_dream_bucket,
    compare_pattern_reliability, decay_confidence_by_age,
)
from .scorer_schema import (
    Metrics, ConfusionDetails, Interpretation, PatternScore, AggregateStatistics,
)

__all__ = [
    "score_patterns_against_traces", "score_patterns_against_dream_bucket",
    "compare_pattern_reliability", "decay_confidence_by_age",
    "Metrics", "ConfusionDetails", "Interpretation", "PatternScore",
    "AggregateStatistics",
]
