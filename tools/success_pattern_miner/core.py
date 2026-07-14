"""tools.success_pattern_miner core (stdlib only).

Mines recurring patterns from *successful* traces: tool sequences, grain
activation patterns, and mixed tool+grain patterns. Builds the SPEC
run-result dict with patterns ranked by frequency. Success filtering and time
windowing delegate to filtering.py; n-gram sliding windows to pattern_extraction.

All functions return JSON-serializable dicts. See SPEC-success_pattern_miner_v1.md.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .filtering import filter_success_traces, is_success
from .pattern_extraction import ngrams

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("success_pattern_miner")
except Exception:  # optional; never let logging break the tool
    _logger = None

_MIN_N, _MAX_N = 2, 6


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return "succ_disc_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _confidence(frequency: int, min_frequency: int, coverage: float) -> float:
    """SPEC heuristic (impl note 6): (freq / min_freq) * (coverage / 0.5), clamp [0,1]."""
    f = frequency / min_frequency if min_frequency else 1.0
    c = coverage / 0.5
    return round(min(1.0, max(0.0, f * c)), 4)


def _discover(seq_field: str, success_traces: List[dict], min_frequency: int
              ) -> List[dict]:
    """Frequency-count n-grams (2..6) of `seq_field`; return ranked patterns."""
    counts: Counter = Counter()
    traces_seen: "OrderedDict[Any, Dict[str, None]]" = OrderedDict()
    first_seen: Dict[Any, str] = {}
    last_seen: Dict[Any, str] = {}
    for t in success_traces:
        seq = t.get(seq_field) or []
        if not seq:
            continue
        tid = t.get("trace_id") or t.get("query_id")
        ts = t.get("timestamp")
        for g in ngrams(seq, _MIN_N, _MAX_N):
            counts[g] += 1
            key = g
            traces_seen.setdefault(key, OrderedDict())
            if tid is not None:
                traces_seen[key].setdefault(tid, None)
            if key not in first_seen or (ts and ts < first_seen[key]):
                first_seen[key] = ts
            if key not in last_seen or (ts and ts > last_seen[key]):
                last_seen[key] = ts

    total_success = len(success_traces)
    patterns: List[dict] = []
    for i, (g, cnt) in enumerate(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])), start=1):
        if cnt < min_frequency:
            continue
        containing = len(traces_seen[g])
        support = round(cnt / total_success, 4) if total_success else 0.0
        coverage = round(containing / total_success, 4) if total_success else 0.0
        patterns.append({
            "pattern_id": f"succ_seq_{i:03d}",
            "sequence": list(g),
            "frequency": cnt,
            "support": support,
            "coverage": coverage,
            "pattern_type": "success_sequence",
            "first_seen": first_seen.get(g),
            "last_seen": last_seen.get(g),
            "confidence_estimate": _confidence(cnt, min_frequency, coverage),
        })
    return patterns


def mine_success_tool_sequences(traces: list, min_frequency: int = 3,
                                success_threshold: float = 0.2,
                                time_window_hours: Optional[int] = None) -> dict:
    """Discover recurring tool sequences in successful traces. See SPEC §API 1."""
    if not isinstance(min_frequency, int) or isinstance(min_frequency, bool) or min_frequency < 1:
        raise ValueError("min_frequency must be an integer >= 1")
    success = filter_success_traces(traces, success_threshold, time_window_hours)
    patterns = _discover("sequence", success, min_frequency)
    return {
        "discovery_run_id": _run_id(),
        "timestamp": _now(),
        "input_traces_count": len(traces),
        "success_traces_count": len(success),
        "patterns": patterns,
        "metadata": {
            "min_frequency_threshold": min_frequency,
            "success_criteria": {"error_signal_max": success_threshold,
                                 "outcome_match": "success"},
            "time_window_hours": time_window_hours,
        },
    }


def mine_success_grain_patterns(traces: list, min_frequency: int = 3,
                                success_threshold: float = 0.2) -> dict:
    """Discover recurring grain activation patterns. See SPEC §API 2."""
    if not isinstance(min_frequency, int) or isinstance(min_frequency, bool) or min_frequency < 1:
        raise ValueError("min_frequency must be an integer >= 1")
    success = filter_success_traces(traces, success_threshold)
    patterns = _discover("grain_activations", success, min_frequency)
    for p in patterns:
        p["pattern_type"] = "success_grain_activation"
        p["pattern_id"] = p["pattern_id"].replace("succ_seq", "succ_grain")
    return {
        "discovery_run_id": _run_id(),
        "timestamp": _now(),
        "input_traces_count": len(traces),
        "success_traces_count": len(success),
        "patterns": patterns,
        "metadata": {
            "min_frequency_threshold": min_frequency,
            "success_criteria": {"error_signal_max": success_threshold,
                                 "outcome_match": "success"},
            "time_window_hours": None,
        },
    }


def mine_mixed_success_patterns(traces: list, min_frequency: int = 3,
                                success_threshold: float = 0.2) -> dict:
    """Discover patterns interleaving tool sequences AND grain activations. See SPEC §API 3."""
    if not isinstance(min_frequency, int) or isinstance(min_frequency, bool) or min_frequency < 1:
        raise ValueError("min_frequency must be an integer >= 1")
    success = filter_success_traces(traces, success_threshold)
    tool_patterns = _discover("sequence", success, min_frequency)
    grain_patterns = _discover("grain_activations", success, min_frequency)
    mixed: List[dict] = []
    for i, (tp, gp) in enumerate(zip(tool_patterns, grain_patterns), start=1):
        freq = min(tp["frequency"], gp["frequency"])
        if freq < min_frequency:
            continue
        coverage = min(tp["coverage"], gp["coverage"])
        mixed.append({
            "pattern_id": f"succ_mixed_{i:03d}",
            "sequence": tp["sequence"],
            "grain_sequence": gp["sequence"],
            "frequency": freq,
            "support": round(freq / len(success), 4) if success else 0.0,
            "coverage": coverage,
            "pattern_type": "success_mixed",
            "first_seen": tp.get("first_seen"),
            "last_seen": tp.get("last_seen"),
            "confidence_estimate": _confidence(freq, min_frequency, coverage),
        })
    return {
        "discovery_run_id": _run_id(),
        "timestamp": _now(),
        "input_traces_count": len(traces),
        "success_traces_count": len(success),
        "patterns": mixed,
        "metadata": {
            "min_frequency_threshold": min_frequency,
            "success_criteria": {"error_signal_max": success_threshold,
                                 "outcome_match": "success"},
            "time_window_hours": None,
        },
    }
