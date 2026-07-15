"""tools.tfidf_ranker core (stdlib only).

TF-IDF vectors + cosine ranking, with three TF weighting variants:
  - standard:   tf = raw term frequency
  - sublinear:  tf = 1 + ln(tf)
  - bm25:       tf = ((k+1)*tf) / (tf + k*(1 - b + b*(dl/avgdl)))   (k=1.5, b=0.75)

IDF (smoothed) shared from inverted_index_builder semantics:
  idf = ln((N - df + 0.5)/(df + 0.5) + 1)

See SPEC-tfidf_ranker_v1.md.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from tools.historical_common import normalize_config, normalize_corpus, now_iso


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _idf(df: int, n_docs: int) -> float:
    return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0) + 1e-9


def _tf_weight(tf: int, variant: str, dl: int, avgdl: float) -> float:
    if variant == "sublinear":
        return 1.0 + math.log(tf) if tf > 0 else 0.0
    if variant == "bm25":
        k, b = 1.5, 0.75
        denom = tf + k * (1 - b + b * (dl / avgdl)) if avgdl > 0 else tf + k
        return ((k + 1) * tf) / denom if tf > 0 else 0.0
    return float(tf)  # standard


def compute_tfidf(corpus: Sequence[dict], config: dict = None) -> dict:
    """Return per-document TF-IDF vectors + idf table."""
    cfg = normalize_config(config)
    variant = cfg.get("tfidf_variant", "standard")
    norm = normalize_corpus(corpus, cfg)
    n_docs = len(norm)
    df_map: Dict[str, int] = defaultdict(int)
    doc_lens = []
    raw_tfs = []
    for doc in norm:
        toks = doc.get("tokens", [])
        doc_lens.append(len(toks))
        tf = Counter(toks)
        raw_tfs.append(tf)
        for t in tf:
            df_map[t] += 1
    avgdl = (sum(doc_lens) / n_docs) if n_docs else 0.0
    idf = {t: _idf(df, n_docs) for t, df in df_map.items()}
    vectors = {}
    for i, doc in enumerate(norm):
        tf = raw_tfs[i]
        dl = doc_lens[i]
        vec = {}
        for t, f in tf.items():
            vec[t] = _tf_weight(f, variant, dl, avgdl) * idf[t]
        vectors[doc.get("id", "")] = vec
    return {
        "tool": "tfidf_ranker", "version": "v1", "run_id": _rid("tfidf"),
        "timestamp": now_iso(),
        "input_summary": {"documents": n_docs, "variant": variant,
                          "vocabulary_size": len(df_map)},
        "idf": idf,
        "document_vectors": vectors,
        "metadata": {"computation_time_ms": 0, "config_used": cfg,
                     "avg_doc_length": round(avgdl, 4)},
    }


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    na = math.sqrt(sum(v * v for v in vec_a.values()))
    nb = math.sqrt(sum(v * v for v in vec_b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def bm25_score(query_tokens: Sequence[str], doc_tokens: Sequence[str],
               idf: Dict[str, float], avgdl: float, k: float = 1.5, b: float = 0.75) -> float:
    """Single-doc BM25 score for a query (idf table precomputed over the corpus)."""
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for t in query_tokens:
        if t not in tf:
            continue
        idf_t = idf.get(t, 0.0)
        f = tf[t]
        denom = f + k * (1 - b + b * (dl / avgdl)) if avgdl > 0 else f + k
        score += idf_t * ((k + 1) * f) / denom
    return score


def rank_documents(query: Sequence[str], corpus: Sequence[dict], config: dict = None) -> dict:
    """Rank corpus docs against a query token list by cosine (or BM25) similarity.

    `tfidf_variant` in config selects 'standard'/'sublinear' (cosine over the
    chosen TF-IDF vectors) or 'bm25' (BM25 scoring directly).
    """
    cfg = normalize_config(config)
    variant = cfg.get("tfidf_variant", "standard")
    norm = normalize_corpus(corpus, cfg)
    n_docs = len(norm)
    # global token-set -> doc-frequency for IDF/BM25
    df_map: Dict[str, int] = defaultdict(int)
    doc_lens = []
    raw_tfs = []
    for doc in norm:
        toks = doc.get("tokens", [])
        doc_lens.append(len(toks))
        tf = Counter(toks)
        raw_tfs.append(tf)
        for t in tf:
            df_map[t] += 1
    avgdl = (sum(doc_lens) / n_docs) if n_docs else 0.0
    idf = {t: _idf(df, n_docs) for t, df in df_map.items()}
    q_tokens = normalize_corpus([{"id": "_q", "tokens": list(query)}], cfg)[0]["tokens"]

    ranked = []
    if variant == "bm25":
        for i, doc in enumerate(norm):
            s = bm25_score(q_tokens, list(raw_tfs[i].elements()), idf, avgdl)
            ranked.append((doc.get("id", ""), s))
    else:
        # cosine over TF-IDF vectors
        q_tf = Counter(q_tokens)
        q_vec = {t: _tf_weight(f, variant, len(q_tokens), 1.0) * idf.get(t, 0.0)
                 for t, f in q_tf.items()}
        for i, doc in enumerate(norm):
            tf = raw_tfs[i]
            dl = doc_lens[i]
            d_vec = {t: _tf_weight(f, variant, dl, avgdl) * idf[t] for t, f in tf.items()}
            ranked.append((doc.get("id", ""), cosine_similarity(q_vec, d_vec)))

    ranked.sort(key=lambda r: (-r[1], r[0]))
    return {
        "tool": "tfidf_ranker", "version": "v1", "run_id": _rid("tfidf_rank"),
        "timestamp": now_iso(),
        "input_summary": {"query_terms": len(q_tokens), "documents": n_docs,
                          "variant": variant, "matching_documents": sum(1 for _, s in ranked if s > 0)},
        "ranking": [{"document_id": did, "score": round(s, 6)} for did, s in ranked],
        "metadata": {"computation_time_ms": 0, "config_used": cfg,
                     "avg_doc_length": round(avgdl, 4)},
    }
