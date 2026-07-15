"""tools.markov_chain — n-gram Markov chain over token sequences (see SPEC).

Build transition counts/probabilities from token sequences, compute entropy,
and generate new sequences with a fixed seed (reproducible). Stateless,
deterministic, stdlib-only.
"""
from .core import build_chain, generate_sequence, compute_entropy, next_token_distribution
from .chain_schema import Transition

__all__ = ["build_chain", "generate_sequence", "compute_entropy",
           "next_token_distribution", "Transition"]
