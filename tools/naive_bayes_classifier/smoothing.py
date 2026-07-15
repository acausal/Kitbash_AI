"""tools.naive_bayes_classifier smoothing helpers (stdlib only).

Laplace (add-one) smoothing for Bernoulli / Multinomial feature estimation.
Core training already applies Laplace inline; this module exposes the primitive
per the SPEC module layout and is used for clarity/testability.
"""
from __future__ import annotations

from typing import Dict


def laplace_prob(count: int, total: int, vocab_size: int) -> float:
    """P(token|class) with Laplace smoothing.

    Bernoulli: total = docs_in_class, vocab_size treated as 2 (binary).
    Multinomial: total = tokens_in_class, vocab_size = V.
    """
    return (count + 1) / (total + vocab_size)


__all__ = ["laplace_prob"]
