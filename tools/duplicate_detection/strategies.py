"""tools.duplicate_detection strategies (stdlib only).

The four pairwise/similarity strategies. Each returns the list of index pairs
(i, j) with i < j that exceed the strategy's threshold. `detect_duplicates`
wires them into connected components.
"""
from __future__ import annotations

import hashlib
from .core import tokenize_text


def _sets(docs, cfg):
    return [set(d["tokens"]) for d in docs]


def exact_keys(docs, cfg):
    """Hashable key per doc: sorted token tuple (multiset-insensitive for exact text)."""
    return [tuple(sorted(d["tokens"])) for d in docs]


def jaccard_pairs(docs, threshold):
    sets = _sets(docs, None)
    n = len(sets)
    pairs = []
    for i in range(n):
        si = sets[i]
        if not si:
            continue
        for j in range(i + 1, n):
            sj = sets[j]
            if not sj:
                continue
            inter = len(si & sj)
            union = len(si | sj)
            if union and inter / union >= threshold:
                pairs.append((i, j))
    return pairs


def shingle_pairs(docs, threshold, k):
    shingles = []
    for d in docs:
        toks = d["tokens"]
        if len(toks) < k:
            sh = {tuple(toks)} if toks else set()
        else:
            sh = {tuple(toks[i:i + k]) for i in range(len(toks) - k + 1)}
        shingles.append(sh)
    n = len(shingles)
    pairs = []
    for i in range(n):
        si = shingles[i]
        if not si:
            continue
        for j in range(i + 1, n):
            sj = shingles[j]
            if not sj:
                continue
            inter = len(si & sj)
            union = len(si | sj)
            if union and inter / union >= threshold:
                pairs.append((i, j))
    return pairs


def _minhash_signature(tokens, h, seed_base=0):
    if not tokens:
        return tuple([0] * h)
    sig = []
    for s in range(h):
        m = min(int(hashlib.md5(f"{s}:{t}".encode()).hexdigest(), 16) for t in tokens)
        sig.append(m)
    return tuple(sig)


def minhash_pairs(docs, threshold, h):
    sigs = [_minhash_signature(d["tokens"], h) for d in docs]
    n = len(sigs)
    pairs = []
    for i in range(n):
        si = sigs[i]
        for j in range(i + 1, n):
            sj = sigs[j]
            eq = sum(1 for a, b in zip(si, sj) if a == b)
            if eq / h >= threshold:
                pairs.append((i, j))
    return pairs
