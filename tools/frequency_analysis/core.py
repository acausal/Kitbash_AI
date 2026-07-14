"""tools.frequency_analysis core (stdlib only).

Pure deterministic frequency statistics over a token stream or tokenized corpus.
See SPEC-frequency_analysis_v1.md.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from tools.historical_common import normalize_config, normalize_token_list, normalize_corpus, now_iso


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _percentile_rank(rank: int, n: int) -> float:
    return round((rank / n) * 100, 2) if n else 0.0


def _coverage_percent(cum: int, total: int) -> float:
    return round((cum / total) * 100, 2) if total else 0.0


def _gini(freqs: List[int]) -> float:
    n = len(freqs)
    total = sum(freqs)
    if n == 0 or total == 0:
        return 0.0
    ordered = sorted(freqs, reverse=True)
    cum = 0
    for i, f in enumerate(ordered, start=1):
        cum += i * f
    return round((2.0 * cum) / (n * total) - (n + 1.0) / n, 4)


def _quantiles(values: List[float], qs=(0.25, 0.5, 0.75, 0.9, 0.99)) -> Dict[str, float]:
    if not values:
        return {}
    s = sorted(values)
    n = len(s)
    out = {}
    for q in qs:
        idx = max(0, min(n - 1, int(q * n) - (0 if q == 1.0 else 1)))
        # linear interpolation between floor and ceil
        pos = q * (n - 1)
        lo = int(pos)
        hi = min(n - 1, lo + 1)
        frac = pos - lo
        val = s[lo] + (s[hi] - s[lo]) * frac
        out[f"q{int(q*100)}"] = round(val, 4)
    return out


def _stats_block(freqs: List[int]) -> Dict[str, float]:
    n = len(freqs)
    if n == 0:
        return {"mean": 0.0, "median": 0.0, "std_dev": 0.0, "min": 0,
                "max": 0, "sum": 0,
                "quantiles": {}}
    s = sorted(freqs)
    total = sum(s)
    mean = total / n
    mid = n // 2
    median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0
    var = sum((x - mean) ** 2 for x in s) / n
    std = math.sqrt(var)
    return {
        "mean": round(mean, 4), "median": round(median, 4),
        "std_dev": round(std, 4), "min": min(s), "max": max(s),
        "sum": total, "quantiles": _quantiles(s),
    }


def analyze_frequencies(tokens: Sequence[str], config: dict = None) -> dict:
    """Frequency + rank + percentile + corpus stats for a flat token stream."""
    cfg = normalize_config(config)
    toks = normalize_token_list(tokens, cfg)
    counter = Counter(toks)
    total = sum(counter.values())
    n_unique = len(counter)
    # rank by frequency desc, tie-break by token for determinism
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    dist = {}
    cum = 0
    for rank, (tok, freq) in enumerate(ranked, start=1):
        cum += freq
        dist[tok] = {
            "frequency": freq,
            "rank": rank,
            "percentile": _percentile_rank(rank, n_unique),
            "coverage_percent": _coverage_percent(cum, total),
        }
    freqs = [freq for _, freq in ranked]
    top_k = max(0, int(cfg.get("top_k", 20)))
    top_tokens = [{"token": t, **dist[t]} for t, _ in ranked[:top_k]]
    bottom_k = int(cfg.get("bottom_k", 5))
    bottom_tokens = [{"token": t, **dist[t]} for t, _ in ranked[-bottom_k:]]
    return {
        "tool": "frequency_analysis", "version": "v1",
        "run_id": _rid("freq"),
        "timestamp": now_iso(),
        "input_summary": {"total_tokens": total, "unique_tokens": n_unique,
                          "avg_frequency": round(total / n_unique, 4) if n_unique else 0.0},
        "frequency_distribution": dist,
        "statistics": {
            "frequency_stats": _stats_block(freqs),
            "token_stats": {
                "total_tokens": total, "unique_tokens": n_unique,
                "type_token_ratio": round(n_unique / total, 4) if total else 0.0,
                "gini_coefficient": _gini(freqs),
            },
        },
        "top_tokens": top_tokens,
        "bottom_tokens": bottom_tokens,
        "metadata": {"computation_time_ms": 0, "config_used": cfg},
    }


def analyze_corpus_frequencies(corpus: Sequence[dict], config: dict = None) -> dict:
    """Document-level frequency stats (total freq, doc freq, per-doc avg)."""
    cfg = normalize_config(config)
    norm = normalize_corpus(corpus, cfg)
    total_freq: Counter = Counter()
    doc_freq: Counter = Counter()
    total_tokens = 0
    for doc in norm:
        toks = doc.get("tokens", [])
        total_tokens += len(toks)
        total_freq.update(toks)
        for t in set(toks):
            doc_freq[t] += 1
    n_unique = len(total_freq)
    ranked = sorted(total_freq.items(), key=lambda kv: (-kv[1], kv[0]))
    dist = {}
    for rank, (tok, tf) in enumerate(ranked, start=1):
        df = doc_freq[tok]
        dist[tok] = {
            "total_frequency": tf,
            "document_frequency": df,
            "avg_frequency_per_doc": round(tf / df, 4),
            "rank": rank,
            "percentile": _percentile_rank(rank, n_unique),
        }
    doc_lengths = [len(d.get("tokens", [])) for d in norm]
    n_docs = len(norm)
    return {
        "tool": "frequency_analysis", "version": "v1",
        "run_id": _rid("freq_corpus"),
        "timestamp": now_iso(),
        "input_summary": {"documents": n_docs, "total_tokens": total_tokens,
                          "unique_tokens": n_unique,
                          "avg_doc_length": round(total_tokens / n_docs, 4) if n_docs else 0.0},
        "frequency_distribution": dist,
        "statistics": {
            "token_frequency_stats": _stats_block(list(total_freq.values())),
            "document_frequency_stats": _stats_block(list(doc_freq.values())),
            "document_length_stats": _stats_block(doc_lengths),
        },
        "metadata": {"computation_time_ms": 0, "config_used": cfg},
    }


def compute_coverage(frequencies: Dict[str, int], coverage_threshold: float = 0.8) -> dict:
    total = sum(frequencies.values())
    ranked = sorted(frequencies.items(), key=lambda kv: (-kv[1], kv[0]))
    cum = 0
    needed = 0
    for tok, f in ranked:
        cum += f
        needed += 1
        if total and cum / total >= coverage_threshold:
            break
    achieved_cum = cum
    # coverage at several thresholds
    cov = {}
    for thr in (0.8, 0.9, 0.95, 0.99):
        cum2 = 0
        cnt = 0
        for tok, f in ranked:
            cum2 += f
            cnt += 1
            if total and cum2 / total >= thr:
                break
        cov[str(int(thr * 100))] = cnt
    return {
        "coverage_analysis": {
            "target_coverage": coverage_threshold,
            "tokens_needed": needed,
            "total_unique_tokens": len(frequencies),
            "coverage_achieved": round(achieved_cum / total, 4) if total else 0.0,
            "coverage_percentages": cov,
        }
    }


def frequency_histogram(frequencies: Dict[str, int], bin_edges: List[float] = None) -> dict:
    if bin_edges is None:
        bin_edges = [1, 2, 5, 10, 50, 100, 1000]
    edges = sorted(bin_edges)
    bins = [{"min": edges[i], "max": edges[i + 1], "count": 0, "tokens_in_bin": []}
            for i in range(len(edges) - 1)]
    for tok, f in frequencies.items():
        placed = False
        for b in bins:
            if b["min"] <= f < b["max"]:
                b["count"] += 1
                b["tokens_in_bin"].append(tok)
                placed = True
                break
        if not placed and f >= edges[-1]:
            b = bins[-1]
            b["count"] += 1
            b["tokens_in_bin"].append(tok)
    return {"histogram": {"bins": bins, "total_tokens": sum(frequencies.values())}}
