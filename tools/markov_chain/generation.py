"""tools.markov_chain generation/analysis helpers (stdlib only).

Secondary helpers per the SPEC module layout. Core model construction lives in
core.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


def top_transitions(chain: dict, context: Sequence[str], top_k: int = 5) -> List[dict]:
    """Top-k most likely next tokens for a context, as [{token, probability}]."""
    from .core import _ctx_key
    t = chain.get("transitions", {}).get(_ctx_key(tuple(context)))
    if not t:
        return []
    ranked = sorted(t["distribution"].items(), key=lambda kv: -kv[1])[:top_k]
    return [{"token": tok, "probability": round(p, 6)} for tok, p in ranked]


def most_uncertain_contexts(entropy_result: dict, top_k: int = 5) -> List[dict]:
    """Contexts with highest entropy (most unpredictable next token)."""
    pc = entropy_result.get("per_context_entropy", {})
    ranked = sorted(pc.items(), key=lambda kv: -kv[1])[:top_k]
    return [{"context": k, "entropy": v} for k, v in ranked]


__all__ = ["top_transitions", "most_uncertain_contexts"]
