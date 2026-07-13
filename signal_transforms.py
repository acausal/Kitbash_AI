"""signal_transforms.py — bounded transforms for decision-making.

SPEC_BOUNDED_SIGNAL_CONSUMPTION: records keep RAW signal values (ground truth,
non-destructive); all DECISIONS (gate trip, penalty magnitude) operate on a
bounded transform. The actual discrimination threshold is DEFERRED (resume
trigger: a body of real, non-synthetic usage sessions exists); re-pick it
empirically from the live distribution then (percentile-based gating is the
documented alternative).

Records written elsewhere (LearningObserver, RecalibrationService) remain RAW.
Only gates/penalties consume the transforms below.
"""
from typing import List

# Operational knob (module constant per codebase convention).
# GATE_THRESHOLD deliberately unchanged from the historical 0.5 — re-picking it
# is the deferred calibration decision, resume trigger documented in SPEC header.
GATE_THRESHOLD: float = 0.5


def bounded_error(raw: float) -> float:
    """Clamp raw mtr_error into [0.0, 1.0] for decision-making.

    Records always store raw; only decisions consume this. Chosen over sigmoid
    for explainability: the live distribution (Task B readout, 2026-07-13) shows
    raw values to ~8.8, and no smooth transform recovers discrimination from an
    uncalibrated signal — that is the deferred threshold decision, not this
    function's job. Negative inputs (seen live on confidence-derived paths)
    clamp to 0.0 instead of producing a negative penalty.
    """
    return max(0.0, min(1.0, raw))


def gate_trips(raw_error: float) -> bool:
    """True iff the raw error should trip the dissonance/consistency gate."""
    return bounded_error(raw_error) > GATE_THRESHOLD


def transform_distribution(raw_values: List[float]) -> List[float]:
    """Map bounded_error over a list of raw values (read-only introspection)."""
    return [bounded_error(v) for v in raw_values]
