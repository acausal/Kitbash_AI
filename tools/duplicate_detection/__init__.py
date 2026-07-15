"""tools.duplicate_detection — duplicate detection over a token corpus (see SPEC).

Public API: `detect_duplicates(corpus, strategy, threshold, keep_strategy, config)`.
Strategies: exact, jaccard, shingle, minhash. Stateless, deterministic, stdlib-only.
"""
from __future__ import annotations

from .core import detect_duplicates, tokenize_text

__all__ = ["detect_duplicates", "tokenize_text"]
