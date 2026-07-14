"""tools.conditional_pattern_detector package.

Library (functions return JSON-serializable dicts):
    from tools.conditional_pattern_detector import (
        detect_conditional_patterns, detect_seeded_patterns,
        extract_decision_trees, filter_patterns, rank_patterns_by_metric,
    )
"""
from .core import (
    detect_conditional_patterns,
    detect_seeded_patterns,
    extract_decision_trees,
    filter_patterns,
    rank_patterns_by_metric,
)
from .pattern_schema import (
    Condition, DecisionNode, DetectionReport, Outcome,
    PatternMetrics, ConditionalPattern, SeedResult,
)

__all__ = [
    "detect_conditional_patterns", "detect_seeded_patterns",
    "extract_decision_trees", "filter_patterns", "rank_patterns_by_metric",
    "Condition", "Outcome", "PatternMetrics", "ConditionalPattern",
    "DetectionReport", "DecisionNode", "SeedResult",
]
