"""tools.positive_signal_scorer signal dimensions (stdlib only).

Each function takes (patterns, traces) and returns per-pattern score dicts.
Pattern matching: a pattern "fires" in a trace when its sequence is a contiguous
subsequence of trace["sequence"] (or trace["grain_sequence"]). Consistency uses
the coefficient of variation of error_signal over firing traces; temporal
stability partitions firing traces into 3 time buckets. See
SPEC-positive_signal_scorer_v1.md §"Signal Dimensions".
"""
from __future__ import annotations

from statistics import pstdev, mean
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _parse_ts(s: Optional[str]):
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _trace_seq(t: dict) -> List[Any]:
    seq = t.get("sequence")
    if seq is None:
        seq = t.get("grain_sequence")
    return seq if isinstance(seq, list) else []


def _fires(pattern: Sequence, tseq: Sequence) -> bool:
    n = len(pattern)
    if n == 0 or len(tseq) < n:
        return False
    for i in range(len(tseq) - n + 1):
        if tseq[i:i + n] == list(pattern):
            return True
    return False


def is_success(t: dict, threshold: float = 0.2) -> bool:
    if t.get("outcome") == "success":
        return True
    err = t.get("error_signal")
    if err is not None:
        try:
            return float(err) < threshold
        except (TypeError, ValueError):
            return False
    return False


def _firing_traces(pattern: Sequence, traces: List[dict]) -> List[dict]:
    return [t for t in traces if _fires(pattern, _trace_seq(t))]


def frequency_score(patterns: List[dict], traces: List[dict]) -> Dict[str, float]:
    """min(frequency / median_frequency_across_patterns, 1.0)."""
    freqs = [p.get("frequency", 0) for p in patterns]
    med = (sorted(freqs)[len(freqs) // 2] if freqs else 0) or 1
    return {p.get("pattern_id"): min(p.get("frequency", 0) / med, 1.0) for p in patterns}


def support_score(patterns: List[dict], traces: List[dict]) -> Dict[str, float]:
    """support is already in the pattern (0..1)."""
    return {p.get("pattern_id"): float(min(max(p.get("support", 0.0), 0.0), 1.0)) for p in patterns}


def outcome_correlation_score(patterns: List[dict], traces: List[dict]
                               ) -> Tuple[Dict[str, float], Dict[str, Tuple[int, int]]]:
    out: Dict[str, float] = {}
    detail: Dict[str, Tuple[int, int]] = {}
    for p in patterns:
        pid = p.get("pattern_id")
        pat = p.get("sequence") or p.get("grain_sequence") or []
        firing = _firing_traces(pat, traces)
        denom = len(firing)
        num = sum(1 for t in firing if is_success(t))
        detail[pid] = (num, denom)
        out[pid] = round(num / denom, 4) if denom else 0.0
    return out, detail


def consistency_score(patterns: List[dict], traces: List[dict]) -> Dict[str, float]:
    """max(1.0 - cv(error_signals of firing traces), 0.0); cv = std/mean."""
    out: Dict[str, float] = {}
    for p in patterns:
        pid = p.get("pattern_id")
        pat = p.get("sequence") or p.get("grain_sequence") or []
        firing = _firing_traces(pat, traces)
        errs = []
        for t in firing:
            e = t.get("error_signal")
            if isinstance(e, (int, float)):
                errs.append(float(e))
        if len(errs) < 2 or mean(errs) == 0:
            out[pid] = 0.0 if not errs else 1.0
            continue
        cv = pstdev(errs) / mean(errs)
        out[pid] = round(max(1.0 - cv, 0.0), 4)
    return out


def _bucketize(traces: List[dict], n_buckets: int = 3) -> List[List[dict]]:
    dated = sorted((_parse_ts(t.get("timestamp")), t) for t in traces
                   if _parse_ts(t.get("timestamp")) is not None)
    if not dated:
        return [[] for _ in range(n_buckets)]
    items = [t for _, t in dated]
    # split as evenly as possible by index into n_buckets
    buckets: List[List[dict]] = [[] for _ in range(n_buckets)]
    for i, t in enumerate(items):
        buckets[min(n_buckets - 1, i * n_buckets // max(len(items), 1))].append(t)
    return buckets


def temporal_stability_score(patterns: List[dict], traces: List[dict]) -> Dict[str, float]:
    """1.0 - (max_bucket_outcome_corr - min_bucket_outcome_corr), clamped."""
    out: Dict[str, float] = {}
    for p in patterns:
        pid = p.get("pattern_id")
        pat = p.get("sequence") or p.get("grain_sequence") or []
        buckets = _bucketize(_firing_traces(pat, traces))
        corrs = []
        for b in buckets:
            denom = len(b)
            if denom == 0:
                continue
            num = sum(1 for t in b if is_success(t))
            corrs.append(num / denom)
        if not corrs:
            out[pid] = 0.0
        else:
            out[pid] = round(max(0.0, 1.0 - (max(corrs) - min(corrs))), 4)
    return out
