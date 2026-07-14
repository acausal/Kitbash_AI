"""tools.frequency_analysis distributions (stdlib only).

Distribution-level helpers: coverage and histogram. Core frequency logic lives in
core.py; this module holds the secondary analytics the SPEC lists as separate
functions so the package matches the contract's module layout.
"""
from __future__ import annotations

from typing import Dict, List

from .core import compute_coverage, frequency_histogram

__all__ = ["coverage", "histogram"]


def coverage(frequencies: Dict[str, int], threshold: float = 0.8) -> dict:
    return compute_coverage(frequencies, threshold)


def histogram(frequencies: Dict[str, int], bin_edges: List[float] = None) -> dict:
    return frequency_histogram(frequencies, bin_edges)
