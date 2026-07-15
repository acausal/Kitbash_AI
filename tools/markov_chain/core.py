"""tools.markov_chain core (stdlib only).

Build an order-n Markov transition model from token sequences, compute per-context
and average entropy, and generate sequences deterministically from a seed.

See SPEC-markov_chain_v1.md.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tools.historical_common import normalize_config, now_iso


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _contexts(seq: Sequence[str], order: int):
    """Yield (context_tuple, next_token) for a sequence given model order."""
    if order <= 0:
        for tok in seq:
            yield (), tok
        return
    for i in range(len(seq) - order):
        ctx = tuple(seq[i:i + order])
        yield ctx, seq[i + order]


def build_chain(sequences: Sequence[Sequence[str]], config: dict = None) -> dict:
    """Build an order-n transition model from a list of token sequences."""
    cfg = normalize_config(config)
    order = int(cfg.get("order", 1))
    smoothing = float(cfg.get("smoothing", 0.0))
    # gather vocabulary for smoothing
    vocab = set()
    for seq in sequences:
        vocab.update(seq)
    V = len(vocab)
    counts: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
    total_pairs = 0
    for seq in sequences:
        toks = list(seq)
        for ctx, nxt in _contexts(toks, order):
            counts[ctx][nxt] += 1
            total_pairs += 1
    # total outgoing count per context (with smoothing spread)
    transitions = {}
    for ctx, ctr in counts.items():
        total_out = sum(ctr.values())
        dist = {}
        for tok, cnt in ctr.items():
            p = (cnt + smoothing) / (total_out + smoothing * V) if (total_out + smoothing * V) > 0 else 0.0
            dist[tok] = p
        # smoothing: add unseen tokens with smoothed prob
        if smoothing > 0 and V > 0:
            for tok in vocab:
                if tok not in dist:
                    dist[tok] = smoothing / (total_out + smoothing * V)
        transitions[ctx] = {"total_out": total_out, "distribution": dist}
    return {
        "tool": "markov_chain", "version": "v1", "run_id": _rid("mc"),
        "timestamp": now_iso(),
        "input_summary": {"sequences": len(sequences), "order": order,
                          "vocabulary_size": V, "total_pairs": total_pairs},
        "transitions": {_ctx_key(ctx): t for ctx, t in transitions.items()},
        "metadata": {"computation_time_ms": 0, "config_used": cfg,
                     "smoothing": smoothing},
    }


def _ctx_key(ctx: Tuple[str, ...]) -> str:
    return "<|>".join(ctx) if ctx else "START"


def _ctx_from_key(key: str) -> Tuple[str, ...]:
    return tuple(key.split("<|>")) if key and key != "START" else ()


def next_token_distribution(chain: dict, context: Sequence[str]) -> dict:
    """Return the next-token distribution for a given context (empty if unseen)."""
    key = _ctx_key(tuple(context))
    t = chain.get("transitions", {}).get(key)
    if not t:
        return {}
    return dict(t["distribution"])


def compute_entropy(chain: dict, config: dict = None) -> dict:
    """Compute entropy per context and the vocabulary-weighted average entropy.

    Entropy here = -sum(p * log2 p) over each context's next-token distribution,
    averaged across contexts (weighted by total_out when requested).
    """
    cfg = normalize_config(config)
    weight_by_count = bool(cfg.get("weight_entropy_by_count", True))
    transitions = chain.get("transitions", {})
    per_context = {}
    weighted_sum = 0.0
    weight_total = 0
    for key, t in transitions.items():
        dist = t["distribution"]
        h = 0.0
        for p in dist.values():
            if p > 0:
                h -= p * math.log2(p)
        per_context[key] = round(h, 6)
        w = t.get("total_out", 1)
        weighted_sum += h * w
        weight_total += w
    avg = weighted_sum / weight_total if (weight_by_count and weight_total) else (
        (sum(per_context.values()) / len(per_context)) if per_context else 0.0)
    return {
        "tool": "markov_chain", "version": "v1", "run_id": _rid("mc_ent"),
        "timestamp": now_iso(),
        "input_summary": {"contexts": len(per_context),
                          "weight_by_count": weight_by_count},
        "average_entropy": round(avg, 6),
        "per_context_entropy": per_context,
        "metadata": {"computation_time_ms": 0},
    }


def generate_sequence(chain: dict, seed_context: Sequence[str] = None,
                      length: int = 10, seed: int = 42, config: dict = None) -> dict:
    """Generate a deterministic token sequence from the model given a seed.

    Reproducible: same chain + seed_context + length + seed -> identical output.
    """
    _ = normalize_config(config)
    rng = random.Random(seed)
    order = chain.get("input_summary", {}).get("order", 1)
    transitions = chain.get("transitions", {})
    if seed_context:
        ctx = list(seed_context)[-order:] if order > 0 else []
    else:
        ctx = []
    out = list(ctx)
    for _ in range(length):
        key = _ctx_key(tuple(ctx))
        t = transitions.get(key)
        if not t or not t["distribution"]:
            # no continuation: try backing off to shorter context
            found = False
            for k in range(len(ctx) - 1, -1, -1):
                sub = tuple(ctx[k:])
                key2 = _ctx_key(sub)
                t2 = transitions.get(key2)
                if t2 and t2["distribution"]:
                    t = t2
                    found = True
                    break
            if not found:
                break
        dist = t["distribution"]
        tokens = list(dist.keys())
        probs = list(dist.values())
        nxt = rng.choices(tokens, weights=probs, k=1)[0]
        out.append(nxt)
        if order > 0:
            ctx = (ctx + [nxt])[-order:]
        else:
            ctx = []
    return {
        "tool": "markov_chain", "version": "v1", "run_id": _rid("mc_gen"),
        "timestamp": now_iso(),
        "input_summary": {"seed_context": list(seed_context) if seed_context else [],
                          "length": length, "seed": seed, "order": order,
                          "generated_tokens": len(out) - len(ctx)},
        "generated_sequence": out,
        "metadata": {"computation_time_ms": 0},
    }
