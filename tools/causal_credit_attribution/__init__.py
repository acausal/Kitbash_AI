"""tools.causal_credit_attribution package.

Attribute success credit to tools/grains within a successful trace using 4
heuristic signals (positional, historical_correlation, pattern_membership,
input_output_salience) combined into per-component credit in [0,1] that sums to
~1.0. Deterministic; no true causality. See SPEC-causal_credit_attribution_v1.md.

Forward-compat hook: pass `tool_metadata={tool: {"work_type": "exploratory"|
"action"|"neutral", "depends_on_results": bool}}` to `attribute_credit_to_tools`
so the CWL brief's custom fields (BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION.md)
are consumed when present; absent -> base salience 0.5.

Library:
    from tools.causal_credit_attribution import (
        attribute_credit_to_tools, attribute_credit_to_grains, batch_attribute_credit)
"""
from .core import (
    attribute_credit_to_tools, attribute_credit_to_grains, batch_attribute_credit,
)
from .attribution_schema import ToolAttribution, GrainAttribution, AttributionResult

__all__ = ["attribute_credit_to_tools", "attribute_credit_to_grains",
           "batch_attribute_credit", "ToolAttribution", "GrainAttribution",
           "AttributionResult"]
