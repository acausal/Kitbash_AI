"""Query completion heuristic for success-signal detection.

Implements the coherence-based success detector from
docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md (Hybrid Stage 1).

Deterministic, zero-friction, conservative: a query completion qualifies as a
"success" only when it is confident, violation-free, sufficiently substantive,
and free of parse errors. Non-blocking by design — callers catch and ignore
failures so answering is never blocked.

Pure-logic module; no I/O. Persistence lives in dream_bucket.py.

Length threshold is QUERY-AWARE (dynamic) by default — a factual yes/no can be
answered in a few words, while an explanation needs substance. Legacy fixed
threshold mode is preserved via an explicit int argument.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Callable, Union


# v1 defaults (tunable). Mirrors SPEC COHERENCE_THRESHOLDS.
# `min_response_length` here is the LEGACY fixed default; the default checker
# uses compute_dynamic_min_length() instead (see CoherenceChecker.__init__).
COHERENCE_THRESHOLDS = {
    "max_violations_allowed": 0,      # Zero violations = success candidate
    "min_top_grain_confidence": 0.60, # MTR top grain must be reasonably confident
    "min_response_length": 100,       # Legacy fixed default (tokens/words)
    "parse_errors_allowed": 0,        # Zero exceptions
}

# Dynamic length thresholds by query type (words). Tunable.
# Factual (Is/Are/What/Who/Where) can be answered briefly; explanations need
# substance. High confidence justifies a shorter answer; low confidence demands
# more to prove reliability.
DYNAMIC_BASE_THRESHOLDS = {
    "factual": 5,
    "explanation": 60,
    "other": 30,
}
HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.60
HIGH_CONF_SCALE = 0.7   # >=0.85 -> 30% shorter allowed
LOW_CONF_SCALE = 1.3    # <0.60  -> 30% longer required


@dataclass
class CoherenceCheckResult:
    """Per-check breakdown + composite error_signal for a completion."""
    passed: bool
    violations_check: bool
    confidence_check: bool
    length_check: bool
    errors_check: bool
    error_signal: float  # [0.0, 1.0]; inverse of confidence when passed, else 1.0
    dynamic_min_length_used: int  # threshold actually applied this check

    def to_dict(self) -> dict:
        return asdict(self)


def compute_dynamic_min_length(query: str, top_grain_confidence: float) -> int:
    """Adaptive minimum response length based on query type and confidence.

    Args:
        query: The user query string.
        top_grain_confidence: MTR confidence of the top-ranked grain [0,1].

    Returns:
        Dynamic threshold in words.

    Logic:
        - Factual queries (is/are/what/who/where/when) accept brief answers.
        - Explanation queries (explain/how/why/describe/tell me about) need
          more substance.
        - High confidence (>=0.85) justifies a ~30% shorter answer.
        - Low confidence (<0.60) requires ~30% more to prove reliability.
    """
    q = (query or "").lower().strip()

    is_factual = any(
        q.startswith(prefix) or f" {prefix}" in q
        for prefix in ("is ", "are ", "what ", "who ", "where ", "when ")
    )
    is_explanation = any(
        tok in q
        for tok in ("explain", "how ", "why ", "describe", "tell me about")
    )

    if is_explanation:
        base = DYNAMIC_BASE_THRESHOLDS["explanation"]
    elif is_factual:
        base = DYNAMIC_BASE_THRESHOLDS["factual"]
    else:
        base = DYNAMIC_BASE_THRESHOLDS["other"]

    if top_grain_confidence >= HIGH_CONFIDENCE:
        return int(base * HIGH_CONF_SCALE)
    if top_grain_confidence < LOW_CONFIDENCE:
        return int(base * LOW_CONF_SCALE)
    return base


class CoherenceChecker:
    """Determines if a query completion qualifies as a success."""

    def __init__(
        self,
        max_violations_allowed: int = COHERENCE_THRESHOLDS["max_violations_allowed"],
        min_top_grain_confidence: float = COHERENCE_THRESHOLDS["min_top_grain_confidence"],
        min_response_length: Union[int, Callable[[str, float], int], None] = None,
        parse_errors_allowed: int = COHERENCE_THRESHOLDS["parse_errors_allowed"],
    ):
        """
        Args:
            min_response_length: length threshold strategy.
                - None (default): dynamic compute_dynamic_min_length(query, conf).
                - int: fixed legacy threshold (constant, ignores query/confidence).
                - Callable: custom function(query, confidence) -> int.
        """
        self.thresholds = {
            "max_violations": max_violations_allowed,
            "min_confidence": min_top_grain_confidence,
            "parse_errors": parse_errors_allowed,
        }
        if min_response_length is None:
            self.min_length_fn = compute_dynamic_min_length
        elif callable(min_response_length):
            self.min_length_fn = min_response_length
        else:
            fixed = int(min_response_length)
            self.min_length_fn = lambda _query, _conf: fixed

    def check(
        self,
        violations_count: int,
        top_grain_confidence: float,
        response_length: int,
        parse_errors: Optional[List[str]] = None,
        query: str = "",
    ) -> CoherenceCheckResult:
        """Run coherence checks on a query completion.

        Args:
            violations_count: # of Dream Bucket violations during this query.
            top_grain_confidence: MTR confidence of the top-ranked grain [0,1].
            response_length: Length of the generated response (words).
            parse_errors: Exceptions raised during response generation.
            query: The original user query (drives the dynamic length threshold).

        Returns:
            CoherenceCheckResult with per-check breakdown + composite error_signal.
            error_signal = (1 - confidence) if all pass, else 1.0.
        """
        parse_errors = parse_errors or []
        violations_ok = violations_count <= self.thresholds["max_violations"]
        confidence_ok = top_grain_confidence >= self.thresholds["min_confidence"]
        min_length = self.min_length_fn(query, top_grain_confidence)
        length_ok = response_length >= min_length
        errors_ok = len(parse_errors) <= self.thresholds["parse_errors"]

        all_passed = violations_ok and confidence_ok and length_ok and errors_ok

        error_signal = (1.0 - top_grain_confidence) if all_passed else 1.0

        return CoherenceCheckResult(
            passed=all_passed,
            violations_check=violations_ok,
            confidence_check=confidence_ok,
            length_check=length_ok,
            errors_check=errors_ok,
            error_signal=error_signal,
            dynamic_min_length_used=min_length,
        )


def generate_trace_id(prefix: str = "succ") -> str:
    """Generate a unique success-trace id (mirrors spec trace_id shape)."""
    from datetime import datetime
    import uuid
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_tr_{stamp}_{uuid.uuid4().hex[:8]}"
