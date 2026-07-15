"""tools.relevance_gate — deterministic query-time relevance filter.

Public API: score_candidates, is_ambiguous, apply_relevance_gate (see core.py).
See docs/SPEC-relevance_gate_v1.md.
"""
from .core import score_candidates, is_ambiguous, apply_relevance_gate

__all__ = ["score_candidates", "is_ambiguous", "apply_relevance_gate"]
