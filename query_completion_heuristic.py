"""Query completion heuristic for success-signal detection.

Implements the coherence-based success detector from
docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md (Hybrid Stage 1).

Deterministic, zero-friction, conservative: a query completion qualifies as a
"success" only when it is confident, violation-free, sufficiently substantive,
and free of parse errors. Non-blocking by design — callers catch and ignore
failures so answering is never blocked.

Pure-logic module; no I/O. Persistence lives in dream_bucket.py.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional


# v1 defaults (tunable). Mirrors SPEC COHERENCE_THRESHOLDS.
COHERENCE_THRESHOLDS = {
    "max_violations_allowed": 0,      # Zero violations = success candidate
    "min_top_grain_confidence": 0.60, # MTR top grain must be reasonably confident
    "min_response_length": 100,       # Minimum tokens to avoid one-liners
    "parse_errors_allowed": 0,        # Zero exceptions
}


@dataclass
class CoherenceCheckResult:
    """Per-check breakdown + composite error_signal for a completion."""
    passed: bool
    violations_check: bool
    confidence_check: bool
    length_check: bool
    errors_check: bool
    error_signal: float  # [0.0, 1.0]; inverse of confidence when passed, else 1.0

    def to_dict(self) -> dict:
        return asdict(self)


class CoherenceChecker:
    """Determines if a query completion qualifies as a success."""

    def __init__(
        self,
        max_violations_allowed: int = COHERENCE_THRESHOLDS["max_violations_allowed"],
        min_top_grain_confidence: float = COHERENCE_THRESHOLDS["min_top_grain_confidence"],
        min_response_length: int = COHERENCE_THRESHOLDS["min_response_length"],
        parse_errors_allowed: int = COHERENCE_THRESHOLDS["parse_errors_allowed"],
    ):
        self.thresholds = {
            "max_violations": max_violations_allowed,
            "min_confidence": min_top_grain_confidence,
            "min_length": min_response_length,
            "parse_errors": parse_errors_allowed,
        }

    def check(
        self,
        violations_count: int,
        top_grain_confidence: float,
        response_length: int,
        parse_errors: Optional[List[str]] = None,
    ) -> CoherenceCheckResult:
        """Run coherence checks on a query completion.

        Args:
            violations_count: # of Dream Bucket violations during this query.
            top_grain_confidence: MTR confidence of the top-ranked grain [0,1].
            response_length: Length of the generated response (tokens).
            parse_errors: Exceptions raised during response generation.

        Returns:
            CoherenceCheckResult with per-check breakdown + composite error_signal.
            error_signal = (1 - confidence) if all pass, else 1.0.
        """
        parse_errors = parse_errors or []
        violations_ok = violations_count <= self.thresholds["max_violations"]
        confidence_ok = top_grain_confidence >= self.thresholds["min_confidence"]
        length_ok = response_length >= self.thresholds["min_length"]
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
        )


def generate_trace_id(prefix: str = "succ") -> str:
    """Generate a unique success-trace id (mirrors spec trace_id shape)."""
    from datetime import datetime
    import uuid
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_tr_{stamp}_{uuid.uuid4().hex[:8]}"
