"""tools.duplicate_detection — duplicate detection over a token corpus (see SPEC).

Four deterministic strategies: exact (sort), jaccard, shingle, minhash.
Stateless, stdlib-only, JSON I/O. See SPEC-duplicate_detection_v1.md.

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
tools.historical_common. Envelope + shared config apply; exit 0/1/2.
"""
from __future__ import annotations

from tools.historical_common import (
    envelope, make_run_id, now_iso, normalize_config,
    normalize_token_list,
)

STRATEGIES = ("exact", "jaccard", "shingle", "minhash")
KEEP = ("first", "shortest", "longest")


def tokenize_text(text, cfg):
    import re
    toks = re.findall(r"\w+", text or "")
    return normalize_token_list(toks, cfg)


def _norm_corpus(corpus, cfg):
    docs = []
    for d in corpus:
        text = d.get("text")
        toks = d.get("tokens")
        if text is not None and toks is None:
            toks = tokenize_text(text, cfg)
        else:
            toks = toks or []
        docs.append({"id": d.get("id", ""), "tokens": list(toks)})
    return docs


def _representative(members, keep):
    if keep == "shortest":
        return min(members, key=lambda m: len(m["tokens"]))
    if keep == "longest":
        return max(members, key=lambda m: len(m["tokens"]))
    # first
    return members[0]


def _components(n, pairs):
    """Union-find over n docs linked by `pairs` (list of (i,j))."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, j in pairs:
        union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def detect_duplicates(corpus, strategy="exact", threshold=1.0,
                      keep_strategy="first", config=None) -> dict:
    cfg = normalize_config(config)
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of {STRATEGIES}")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold {threshold} out of range [0, 1]")
    if keep_strategy not in KEEP:
        raise ValueError(f"unknown keep_strategy {keep_strategy!r}; expected one of {KEEP}")
    if not corpus:
        raise ValueError("empty corpus")
    docs = _norm_corpus(corpus, cfg)
    n = len(docs)

    from .strategies import exact_keys, jaccard_pairs, shingle_pairs, minhash_pairs

    if strategy == "exact":
        keys = exact_keys(docs, cfg)
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n) if keys[i] == keys[j]]
        groups = _components(n, pairs)
    elif strategy == "jaccard":
        pairs = jaccard_pairs(docs, threshold)
        groups = _components(n, pairs)
    elif strategy == "shingle":
        pairs = shingle_pairs(docs, threshold, int(cfg.get("shingle_size", 3)))
        groups = _components(n, pairs)
    else:  # minhash
        pairs = minhash_pairs(docs, threshold, int(cfg.get("minhash_hashes", 64)))
        groups = _components(n, pairs)

    dup_groups = []
    for gi, members in enumerate(groups):
        if len(members) < 2:
            continue
        mdoc = [_mk_member(docs[i]) for i in members]
        rep = _representative(mdoc, keep_strategy)
        dup_groups.append({
            "group_id": len(dup_groups),
            "members": [m["id"] for m in mdoc],
            "representative": rep["id"],
            "member_tokens": {m["id"]: len(m["tokens"]) for m in mdoc},
        })

    total_dups = sum(len(g["members"]) for g in dup_groups)
    return {
        **envelope("duplicate_detection"),
        "input_summary": {
            "document_count": n,
            "strategy": strategy,
            "threshold": threshold,
            "keep_strategy": keep_strategy,
        },
        "duplicate_groups": dup_groups,
        "summary": {
            "duplicate_group_count": len(dup_groups),
            "total_duplicate_documents": total_dups,
        },
    }


def _mk_member(doc):
    return {"id": doc["id"], "tokens": doc["tokens"]}
