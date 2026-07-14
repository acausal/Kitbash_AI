"""tools.pattern_explainer package.

Library:
    from tools.pattern_explainer import (
        explain_collision_cluster,
        explain_anomaly,
        explain_pattern_reliability,
        explain_multiple_patterns,
        generate_sleep_report,
    )

CLI:
    python -m tools.pattern_explainer explain-cluster --cluster c.json
    python -m tools.pattern_explainer explain-anomaly --anomaly a.json
    python -m tools.pattern_explainer explain-pattern --pattern p.json --confidence-scores s.json
    python -m tools.pattern_explainer explain-patterns --patterns p.json --confidence-scores s.json --summary-style brief
    python -m tools.pattern_explainer generate-sleep-report --collision-clusters c.json --anomalies a.json --patterns p.json --confidence-scores s.json

Stdlib only (json, string). Exit codes: 0 success, 1 ValueError, 2 RuntimeError.
"""
from .core import (
    explain_collision_cluster,
    explain_anomaly,
    explain_pattern_reliability,
    explain_multiple_patterns,
    generate_sleep_report,
)
from .confidence_language import (
    severity_to_label,
    f1_to_reliability,
    cluster_confidence_label,
    pattern_confidence_label,
)
from .formatters import (
    format_percentage,
    format_magnitude,
    format_confidence,
    format_list,
    format_timestamp,
    format_entity_label,
    format_pattern_sequence,
)

__all__ = [
    "explain_collision_cluster",
    "explain_anomaly",
    "explain_pattern_reliability",
    "explain_multiple_patterns",
    "generate_sleep_report",
    "severity_to_label",
    "f1_to_reliability",
    "cluster_confidence_label",
    "pattern_confidence_label",
    "format_percentage",
    "format_magnitude",
    "format_confidence",
    "format_list",
    "format_timestamp",
    "format_entity_label",
    "format_pattern_sequence",
]
