"""tools.success_pattern_miner pattern extraction (stdlib only).

Pure n-gram helpers over a trace's `sequence` (tools) or `grain_activations`
(int ids). No I/O, no filtering — just sliding windows. See
SPEC-success_pattern_miner_v1.md impl note 2 (n-grams length 2–6).
"""
from typing import Any, List, Tuple


def ngrams(seq, min_n: int = 2, max_n: int = 6) -> List[Tuple]:
    """Contiguous n-grams of length min_n..max_n over `seq` (inclusive).

    Returns a flat list of tuples; an n-gram that appears k times adds k tuples
    (so callers can frequency-count by occurrence). Short sequences that can't
    yield an n-gram of length n contribute nothing for that n.
    """
    if seq is None:
        seq = []
    if not isinstance(seq, list):
        raise ValueError("sequence must be a list")
    if not isinstance(min_n, int) or isinstance(min_n, bool) or min_n < 1:
        raise ValueError("min_n must be an integer >= 1")
    if not isinstance(max_n, int) or isinstance(max_n, bool) or max_n < 1:
        raise ValueError("max_n must be an integer >= 1")
    if max_n < min_n:
        raise ValueError("max_n must be >= min_n")
    L = len(seq)
    out: List[Tuple] = []
    for n in range(min_n, max_n + 1):
        if L < n:
            continue
        for i in range(L - n + 1):
            out.append(tuple(seq[i:i + n]))
    return out
