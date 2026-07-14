"""tools.positive_signal_scorer package.

Score success patterns (from Success Pattern Miner) on 5 signal dimensions —
frequency, support, outcome_correlation, consistency, temporal_stability — and
combine into a composite signal_strength in [0,1]. Deterministic; no statistics
beyond stdlib. See SPEC-positive_signal_scorer_v1.md.

Library:
    from tools.positive_signal_scorer import score_patterns, compute_signal_dimension
    result = score_patterns(patterns, traces, weights=None)
    dim = compute_signal_dimension(patterns, traces, "outcome_correlation")
"""
from .core import score_patterns, compute_signal_dimension
from .scorer_schema import ScoredPattern, DimensionScore, ScoreResult

__all__ = ["score_patterns", "compute_signal_dimension",
           "ScoredPattern", "DimensionScore", "ScoreResult"]
