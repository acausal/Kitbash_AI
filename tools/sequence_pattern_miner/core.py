"""sequence_pattern_miner core: mine frequent n-gram sequences from traces.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

Consumes normalized traces (from log_parser). Elements are the prefixed
"<type>_<id>" form (e.g. "fact_123"), consistent with log_parser aggregation.
All functions return JSON-serializable dicts. Simple frequency counting; no
statistical tests (v1).
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from typing import Any, Dict, List, Optional, Tuple

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("sequence_pattern_miner")
except Exception:  # optional; never let logging break the tool
    _logger = None

_CHAIN_FILTERS = ("fact_only", "grain_only", "mixed")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _prefixed(step: dict) -> str:
    return f"{step.get('element_type', 'unknown')}_{step.get('element_id')}"


def _chain_types(chain: List[dict]) -> List[str]:
    return [s.get("element_type", "unknown") for s in chain]


def _chain_matches_filter(chain: List[dict], chain_filter: Optional[str]) -> bool:
    if chain_filter is None:
        return True
    types = set(_chain_types(chain))
    if chain_filter == "fact_only":
        return types == {"fact"}
    if chain_filter == "grain_only":
        return types == {"grain"}
    if chain_filter == "mixed":
        return "fact" in types and "grain" in types
    return True  # unreachable (validated by caller)


def _seq_type(types: Tuple[str, ...]) -> str:
    """Homogeneous or 2-element -> joined types; 3+ heterogeneous -> 'mixed'."""
    uniq = set(types)
    if len(uniq) == 1:
        return "→".join(types)
    if len(types) == 2:
        return "→".join(types)
    return "mixed"


def _validate_traces(traces) -> None:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")


def _validate_sequences(sequences) -> None:
    if not isinstance(sequences, list):
        raise ValueError("sequences must be a list")


# --------------------------------------------------------------------------- #
# 1. extract_ngrams
# --------------------------------------------------------------------------- #
def extract_ngrams(traces: list, n: int = 2, min_frequency: int = 1,
                   chain_filter: str = None) -> dict:
    """Extract n-grams from traces, optionally filtering by chain composition.

    chain_filter (trace-level, not element-level):
      None -> all traces; "fact_only" -> traces whose steps are ALL facts;
      "grain_only" -> ALL grains; "mixed" -> traces with both fact and grain.
    Non-matching traces are skipped entirely.
    """
    _validate_traces(traces)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be an integer >= 1")
    if not isinstance(min_frequency, int) or isinstance(min_frequency, bool) or min_frequency < 1:
        raise ValueError("min_frequency must be an integer >= 1")
    if chain_filter is not None and chain_filter not in _CHAIN_FILTERS:
        raise ValueError(f"chain_filter must be one of {_CHAIN_FILTERS} or None")

    counts: Counter = Counter()
    type_lookup: Dict[Tuple[str, ...], str] = {}
    traces_containing: Dict[Tuple[str, ...], "OrderedDict[str, None]"] = {}
    chains_analyzed = 0
    total_ngrams = 0

    for t in traces:
        if not isinstance(t, dict) or "chain" not in t:
            raise RuntimeError("invalid trace structure: missing 'chain'")
        chain = t.get("chain") or []
        if not _chain_matches_filter(chain, chain_filter):
            continue
        chains_analyzed += 1
        if len(chain) < n:
            continue
        elems = [_prefixed(s) for s in chain]
        types = _chain_types(chain)
        tid = t.get("trace_id") or t.get("query_id")
        for i in range(len(elems) - n + 1):
            seq = tuple(elems[i:i + n])
            counts[seq] += 1
            total_ngrams += 1
            if seq not in type_lookup:
                type_lookup[seq] = _seq_type(tuple(types[i:i + n]))
            traces_containing.setdefault(seq, OrderedDict())
            if tid is not None:
                traces_containing[seq].setdefault(tid, None)

    # filter + rank (desc by count, tie-break by sequence for determinism)
    kept = [(seq, c) for seq, c in counts.items() if c >= min_frequency]
    kept.sort(key=lambda kv: (-kv[1], kv[0]))
    sequences = []
    for rank, (seq, cnt) in enumerate(kept, start=1):
        tids = list(traces_containing.get(seq, {}))
        sequences.append({
            "rank": rank,
            "sequence": list(seq),
            "sequence_type": type_lookup[seq],
            "occurrence_count": cnt,
            "frequency_percent": round(cnt / total_ngrams * 100, 2) if total_ngrams else 0.0,
            "traces_containing": tids,
            "first_observed_trace": tids[0] if tids else None,
            "last_observed_trace": tids[-1] if tids else None,
        })

    all_counts = list(counts.values())
    stats = {
        "total_chains_analyzed": chains_analyzed,
        "total_ngrams_extracted": total_ngrams,
        "unique_sequences": len(counts),
        "most_common_frequency": max(all_counts) if all_counts else 0,
        "least_common_frequency": min(all_counts) if all_counts else 0,
        "average_frequency": round(sum(all_counts) / len(all_counts), 2) if all_counts else 0.0,
    }
    if _logger:
        _logger.log(event_type="extraction_complete",
                    data={"traces_analyzed": chains_analyzed,
                          "ngrams_extracted": total_ngrams,
                          "unique_sequences": len(counts)})
    return {
        "extraction_params": {
            "n": n, "min_frequency": min_frequency,
            "chain_filter": chain_filter, "total_traces": len(traces),
        },
        "statistics": stats,
        "sequences": sequences,
    }


# --------------------------------------------------------------------------- #
# 2. extract_ngrams_by_length
# --------------------------------------------------------------------------- #
def extract_ngrams_by_length(traces: list, min_n: int = 1, max_n: int = 4,
                             min_frequency: int = 1) -> dict:
    _validate_traces(traces)
    if not isinstance(min_n, int) or isinstance(min_n, bool) or min_n < 1:
        raise ValueError("min_n must be an integer >= 1")
    if not isinstance(max_n, int) or isinstance(max_n, bool) or max_n < 1:
        raise ValueError("max_n must be an integer >= 1")
    if max_n < min_n:
        raise ValueError("max_n must be >= min_n")

    by_length: Dict[str, dict] = {}
    total_extracted = 0
    unique_total = 0
    overall_best_seq = None
    overall_best_freq = 0
    for n in range(min_n, max_n + 1):
        res = extract_ngrams(traces, n=n, min_frequency=min_frequency)
        seqs = res["sequences"]
        total_this = res["statistics"]["total_ngrams_extracted"]
        unique_this = res["statistics"]["unique_sequences"]
        total_extracted += total_this
        unique_total += unique_this
        entry = {
            f"total_{_ngram_word(n)}": total_this,
            f"unique_{_ngram_word(n)}": unique_this,
            "sequences": seqs,
        }
        by_length[f"n={n}"] = entry
        if seqs and seqs[0]["occurrence_count"] > overall_best_freq:
            overall_best_freq = seqs[0]["occurrence_count"]
            overall_best_seq = seqs[0]["sequence"]

    return {
        "extraction_params": {
            "min_n": min_n, "max_n": max_n,
            "min_frequency": min_frequency, "total_traces": len(traces),
        },
        "sequences_by_length": by_length,
        "summary": {
            "total_sequences_extracted": total_extracted,
            "total_unique_sequences": unique_total,
            "most_common_sequence": overall_best_seq,
            "most_common_frequency": overall_best_freq,
        },
    }


def _ngram_word(n: int) -> str:
    return {1: "unigrams", 2: "bigrams", 3: "trigrams"}.get(n, f"{n}grams")


# --------------------------------------------------------------------------- #
# 3. filter_sequences
# --------------------------------------------------------------------------- #
def filter_sequences(sequences: list, min_frequency: int,
                     max_frequency: int = None) -> dict:
    _validate_sequences(sequences)
    if not isinstance(min_frequency, int) or isinstance(min_frequency, bool) or min_frequency < 1:
        raise ValueError("min_frequency must be an integer >= 1")
    if max_frequency is not None:
        if not isinstance(max_frequency, int) or isinstance(max_frequency, bool):
            raise ValueError("max_frequency must be an integer")
        if min_frequency > max_frequency:
            raise ValueError("min_frequency must be <= max_frequency")

    kept = []
    for s in sequences:
        c = s.get("occurrence_count", 0)
        if c < min_frequency:
            continue
        if max_frequency is not None and c > max_frequency:
            continue
        kept.append(s)
    kept.sort(key=lambda s: (-s.get("occurrence_count", 0), s.get("sequence", [])))
    for rank, s in enumerate(kept, start=1):
        s = dict(s)
        s["rank"] = rank
        kept[rank - 1] = s
    return {
        "filter_criteria": {"min_frequency": min_frequency, "max_frequency": max_frequency},
        "total_sequences_input": len(sequences),
        "sequences_after_filtering": len(kept),
        "filtered_out": len(sequences) - len(kept),
        "sequences": kept,
    }


# --------------------------------------------------------------------------- #
# 4. rank_sequences_by_element_type
# --------------------------------------------------------------------------- #
def rank_sequences_by_element_type(sequences: list) -> dict:
    _validate_sequences(sequences)
    by_type: Dict[str, List[dict]] = {}
    for s in sequences:
        st = s.get("sequence_type", "unknown")
        by_type.setdefault(st, []).append(s)

    out: Dict[str, dict] = {}
    total = len(sequences)
    dist: Dict[str, float] = {}
    for st, seqs in by_type.items():
        seqs_sorted = sorted(seqs, key=lambda s: (-s.get("occurrence_count", 0), s.get("sequence", [])))
        top = [{"rank": i + 1, "sequence": s.get("sequence", []),
                "occurrence_count": s.get("occurrence_count", 0)}
               for i, s in enumerate(seqs_sorted[:10])]
        out[st] = {"count": len(seqs), "top_sequences": top}
        dist[st] = round(len(seqs) / total * 100, 1) if total else 0.0
    return {
        "sequences_by_type": out,
        "summary": {"total_sequences": total, "type_distribution": dist},
    }


# --------------------------------------------------------------------------- #
# 5. sequences_to_markov_transitions
# --------------------------------------------------------------------------- #
def sequences_to_markov_transitions(sequences: list) -> dict:
    _validate_sequences(sequences)
    # accumulate source -> target -> count (bigrams only)
    src_tgt: Dict[str, "Counter"] = {}
    for s in sequences:
        seq = s.get("sequence", [])
        if len(seq) != 2:
            continue
        cnt = s.get("occurrence_count", 0)
        source, target = seq[0], seq[1]
        src_tgt.setdefault(source, Counter())[target] += cnt

    transitions: Dict[str, Dict[str, dict]] = {}
    total_transitions = 0
    for source, targets in src_tgt.items():
        out_total = sum(targets.values())
        total_transitions += out_total
        transitions[source] = {}
        for target, cnt in sorted(targets.items(), key=lambda kv: (-kv[1], kv[0])):
            prob = cnt / out_total if out_total else 0.0
            transitions[source][target] = {
                "transition_count": cnt,
                "transition_probability": round(prob, 4),
                "frequency_percent": round(prob * 100, 2),
            }
    return {
        "transitions": transitions,
        "state_count": len(transitions),
        "total_transitions": total_transitions,
    }
