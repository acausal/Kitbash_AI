"""tools.inverted_index_builder core (stdlib only).

Pure deterministic inverted index construction over a tokenized corpus.
See SPEC-inverted_index_builder_v1.md.

Output shape (from the SPEC):
  {
    "tool": "inverted_index_builder", "version": "v1", "run_id", "timestamp",
    "input_summary": {"documents": N, "total_tokens": T, "unique_tokens": V,
                      "avg_doc_length": float},
    "index": {
       token: {"document_frequency": int, "postings": [{"doc_id":..., "term_frequency":int}]}
    },
    "idf_values": { token: float },
    "metadata": {...}
  }
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from tools.historical_common import normalize_config, normalize_corpus, now_iso


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _idf(df: int, n_docs: int, scheme: str = "standard", eps: float = 1e-9) -> float:
    """Standard IDF = ln((N - df + 0.5) / (df + 0.5) + 1). Smoothing avoids log0."""
    if scheme == "probabilistic":
        return max(0.0, math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0))
    if scheme == "log":
        return math.log(n_docs / (df + 1.0)) + 1.0
    # standard (default) — smoothed inverse doc frequency
    return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0) + eps * 0.0


def build_index(corpus: Sequence[dict], config: dict = None) -> dict:
    """Build a TF/DF inverted index from a tokenized document corpus."""
    cfg = normalize_config(config)
    norm = normalize_corpus(corpus, cfg)
    n_docs = len(norm)
    index: Dict[str, Dict[str, Any]] = {}
    total_tokens = 0
    for doc in norm:
        doc_id = doc.get("id", "")
        toks = doc.get("tokens", [])
        total_tokens += len(toks)
        tf = Counter(toks)
        for tok, freq in tf.items():
            entry = index.setdefault(tok, {"document_frequency": 0, "postings": []})
            entry["postings"].append({"doc_id": doc_id, "term_frequency": freq})
            entry["document_frequency"] += 1
    # sort postings by doc_id for determinism
    for tok, entry in index.items():
        entry["postings"].sort(key=lambda p: p["doc_id"])
    idf_scheme = cfg.get("idf_scheme", "standard")
    idf_values = {tok: _idf(e["document_frequency"], n_docs, idf_scheme)
                  for tok, e in index.items()}
    n_unique = len(index)
    return {
        "tool": "inverted_index_builder", "version": "v1",
        "run_id": _rid("iib"),
        "timestamp": now_iso(),
        "input_summary": {
            "documents": n_docs,
            "total_tokens": total_tokens,
            "unique_tokens": n_unique,
            "avg_doc_length": round(total_tokens / n_docs, 4) if n_docs else 0.0,
        },
        "index": index,
        "idf_values": idf_values,
        "metadata": {"computation_time_ms": 0, "config_used": cfg,
                     "idf_scheme": idf_scheme},
    }


def compute_idf(document_frequencies: Dict[str, int], total_documents: int,
                idf_scheme: str = "standard") -> dict:
    """Compute IDF for a {token: df} map. Pure helper (no corpus needed)."""
    return {tok: _idf(df, total_documents, idf_scheme)
            for tok, df in document_frequencies.items()}


def add_document(index: dict, doc: dict, config: dict = None) -> dict:
    """Return a NEW index with `doc` merged in (stateless: input index unchanged)."""
    cfg = normalize_config(config)
    norm = normalize_corpus([doc], cfg)[0]
    doc_id = norm.get("id", "")
    toks = norm.get("tokens", [])
    tf = Counter(toks)
    base_index = index.get("index", {})
    new_index = {tok: {"document_frequency": e["document_frequency"],
                       "postings": list(e["postings"])}
                 for tok, e in base_index.items()}
    for tok, freq in tf.items():
        entry = new_index.setdefault(tok, {"document_frequency": 0, "postings": []})
        entry["postings"].append({"doc_id": doc_id, "term_frequency": freq})
        entry["document_frequency"] += 1
    n_docs = index.get("input_summary", {}).get("documents", 0) + 1
    idf_scheme = (index.get("metadata", {}) or {}).get("idf_scheme", "standard")
    idf_values = {tok: _idf(e["document_frequency"], n_docs, idf_scheme)
                  for tok, e in new_index.items()}
    return {
        **{k: v for k, v in index.items() if k not in ("index", "idf_values", "input_summary", "metadata")},
        "input_summary": {**index.get("input_summary", {}), "documents": n_docs},
        "index": new_index,
        "idf_values": idf_values,
        "metadata": {**(index.get("metadata") or {}), "idf_scheme": idf_scheme},
    }


def merge_indexes(indexes: Sequence[dict], config: dict = None) -> dict:
    """Merge multiple index outputs into one (union postings, recompute DF/IDF)."""
    cfg = normalize_config(config)
    merged: Dict[str, Dict[str, Any]] = {}
    n_docs = 0
    seen_docs = set()
    for idx in indexes:
        n_docs += idx.get("input_summary", {}).get("documents", 0)
        for tok, e in idx.get("index", {}).items():
            entry = merged.setdefault(tok, {"document_frequency": 0, "postings": []})
            entry["postings"].extend(e["postings"])
            entry["document_frequency"] += e["document_frequency"]
            for p in e["postings"]:
                seen_docs.add(p["doc_id"])
    for tok, entry in merged.items():
        entry["postings"].sort(key=lambda p: p["doc_id"])
    idf_scheme = cfg.get("idf_scheme", "standard")
    idf_values = {tok: _idf(e["document_frequency"], n_docs, idf_scheme)
                  for tok, e in merged.items()}
    return {
        "tool": "inverted_index_builder", "version": "v1",
        "run_id": _rid("iib_merge"),
        "timestamp": now_iso(),
        "input_summary": {"documents": n_docs, "unique_doc_ids": len(seen_docs),
                          "unique_tokens": len(merged)},
        "index": merged,
        "idf_values": idf_values,
        "metadata": {"computation_time_ms": 0, "config_used": cfg, "idf_scheme": idf_scheme},
    }
