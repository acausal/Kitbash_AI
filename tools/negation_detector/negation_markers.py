"""Negation markers for tools.negation_detector (v1).

spaCy splits contractions (e.g. "don't" -> ["do", "n't"]); the "n't" token has
lemma "not", so contraction negation is caught via lemma matching. Whole-word
contractions therefore don't need listing here.
"""
from __future__ import annotations

NEGATION_MARKERS: frozenset[str] = frozenset({
    "not", "no", "never", "neither", "nor",
})


def is_negation_marker(text: str, lemma: str) -> bool:
    """True if a token (by surface text or lemma, case-insensitive) negates."""
    return text.lower() in NEGATION_MARKERS or lemma.lower() in NEGATION_MARKERS
