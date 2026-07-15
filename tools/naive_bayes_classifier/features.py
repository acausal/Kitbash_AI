"""Feature extraction for tools.naive_bayes_classifier (stdlib only).

Bernoulli: token present/absent per document. Multinomial: token frequency.
Shared config (lowercase/stopwords) from historical_common.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Sequence

from tools.historical_common import normalize_config, normalize_token_list


def bernoulli_features(tokens: Sequence[str], config: dict = None) -> set:
    """Set of distinct tokens present in the document."""
    cfg = normalize_config(config)
    return set(normalize_token_list(tokens, cfg))


def multinomial_features(tokens: Sequence[str], config: dict = None) -> Counter:
    """Token frequency counter for the document."""
    cfg = normalize_config(config)
    return Counter(normalize_token_list(tokens, cfg))
