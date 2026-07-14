"""log_parser core: ingest + normalize execution traces for pattern mining.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib and Kitbash
core's structured_logger (read-only helper). No orchestrator/engine/redis imports.

Design: lenient streaming parse (skip/log bad lines), strict validation (fail on
missing required fields). All functions return JSON-serializable dicts. Chain-step
element_id is kept raw; aggregate/transition sequences use the prefixed form
"<type>_<id>" (e.g. "fact_123") per the SPEC output examples.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("log_parser")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_timestamp(ts: str) -> str:
    """Raise ValueError if ts is not a parseable ISO 8601 string; return it."""
    txt = ts[:-1] + "+00:00" if isinstance(ts, str) and ts.endswith("Z") else ts
    try:
        datetime.fromisoformat(txt)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid timestamp format: {ts!r}")
    return ts


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
def _normalize_step(raw: dict, position: int) -> Optional[dict]:
    """Normalize a single chain step. Returns None if malformed (skip)."""
    if not isinstance(raw, dict):
        return None
    has_fact = "fact_id" in raw and raw["fact_id"] is not None
    has_grain = "grain_id" in raw and raw["grain_id"] is not None
    if has_fact:  # fact takes precedence on ambiguity
        element_id, element_type = raw["fact_id"], "fact"
    elif has_grain:
        element_id, element_type = raw["grain_id"], "grain"
    elif raw.get("element_id") is not None:
        element_id = raw["element_id"]
        element_type = raw.get("element_type", "unknown")
    else:
        return None  # no id -> skip step (logged by caller)
    step = {
        "position": position,
        "element_id": element_id,
        "element_type": element_type,
        "traversal_type": raw.get("traversal_type", "unknown"),
    }
    for opt in ("cartridge", "timestamp", "weight"):
        if raw.get(opt) is not None:
            step[opt] = raw[opt]
    return step


def normalize_trace(raw_trace: dict) -> dict:
    """Apply normalization rules to a raw trace (exported for testing)."""
    if not isinstance(raw_trace, dict):
        raise ValueError("trace must be a JSON object")
    if not raw_trace.get("query_id"):
        raise ValueError("trace missing required field: query_id")
    if not isinstance(raw_trace["query_id"], str):
        raise ValueError("query_id must be a string")
    chain_raw = raw_trace.get("chain")
    if not chain_raw or not isinstance(chain_raw, list):
        raise ValueError("trace missing required non-empty field: chain")
    chain_type = raw_trace.get("chain_type")
    if not chain_type:
        raise ValueError("trace missing required field: chain_type")

    ts = raw_trace.get("timestamp")
    ts = _validate_timestamp(ts) if ts else _now_iso()

    norm_chain: List[dict] = []
    pos = 0
    for raw_step in chain_raw:
        step = _normalize_step(raw_step, pos)
        if step is None:
            if _logger:
                _logger.log(event_type="parsing_failed",
                            data={"warning": "malformed chain step skipped",
                                  "query_id": raw_trace["query_id"]})
            continue
        norm_chain.append(step)
        pos += 1

    query_id = raw_trace["query_id"]
    return {
        "trace_id": raw_trace.get("trace_id") or query_id,
        "query_id": query_id,
        "chain_type": chain_type,
        "session_id": raw_trace.get("session_id"),
        "timestamp": ts,
        "chain": norm_chain,
        "chain_length": len(norm_chain),
        "context": raw_trace.get("context") or {},
    }


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_json_trace(json_str: str) -> dict:
    if not isinstance(json_str, str):
        raise ValueError("json_str must be a string")
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}")
    return normalize_trace(raw)


def parse_jsonl_traces(jsonl_content: str) -> dict:
    if not isinstance(jsonl_content, str):
        raise ValueError("jsonl_content must be a string")
    total_lines = 0
    valid: List[dict] = []
    errors: List[dict] = []
    for i, line in enumerate(jsonl_content.splitlines(), start=1):
        if not line.strip():
            continue  # skip blank lines
        total_lines += 1
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append({"line_number": i, "error": f"JSONDecodeError: {e}",
                           "line_content": line[:200]})
            continue
        try:
            valid.append(normalize_trace(raw))
        except ValueError as e:
            errors.append({"line_number": i, "error": f"ValueError: {e}",
                           "line_content": line[:200]})
    report = {
        "total_lines": total_lines,
        "valid_traces": len(valid),
        "invalid_lines": len(errors),
        "errors": errors,
    }
    if _logger:
        _logger.log(event_type="parsing_complete",
                    data={"traces_read": total_lines, "traces_output": len(valid),
                          "errors_logged": len(errors)})
    return {"parsing_report": report, "traces": valid}


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def filter_traces(traces: list, filters: dict) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    filters = filters or {}
    if not isinstance(filters, dict):
        raise ValueError("filters must be a dict")

    min_ts = filters.get("min_timestamp")
    max_ts = filters.get("max_timestamp")
    if min_ts and max_ts and min_ts > max_ts:
        raise ValueError("min_timestamp must be <= max_timestamp")
    min_len = filters.get("min_chain_length")
    max_len = filters.get("max_chain_length")
    if min_len is not None and max_len is not None and min_len > max_len:
        raise ValueError("min_chain_length must be <= max_chain_length")
    session_ids = filters.get("session_ids")
    chain_type = filters.get("chain_type")
    element_types = filters.get("element_types")
    cartridges = filters.get("cartridges")

    def keep(t: dict) -> bool:
        ts = t.get("timestamp", "")
        if min_ts and ts < min_ts:
            return False
        if max_ts and ts > max_ts:
            return False
        if session_ids and t.get("session_id") not in session_ids:
            return False
        if chain_type and t.get("chain_type") != chain_type:
            return False
        cl = t.get("chain_length", 0)
        if min_len is not None and cl < min_len:
            return False
        if max_len is not None and cl > max_len:
            return False
        if element_types:
            types = {s.get("element_type") for s in t.get("chain", [])}
            if not (set(element_types) & types):
                return False
        if cartridges:
            carts = {s.get("cartridge") for s in t.get("chain", [])}
            carts.add((t.get("context") or {}).get("cartridge"))
            if not (set(cartridges) & carts):
                return False
        return True

    kept = [t for t in traces if keep(t)]
    if _logger:
        _logger.log(event_type="filtering_started",
                    data={"input": len(traces), "output": len(kept)})
    return {
        "filter_criteria": filters,
        "total_traces_input": len(traces),
        "traces_after_filtering": len(kept),
        "filtered_out": len(traces) - len(kept),
        "traces": kept,
    }


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _prefixed(step: dict) -> str:
    return f"{step.get('element_type','unknown')}_{step.get('element_id')}"


def _seq_type(types: List[str]) -> str:
    uniq = set(types)
    if uniq == {"fact"}:
        return "fact"
    if uniq == {"grain"}:
        return "grain"
    return "mixed"


def aggregate_chains(traces: list) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    counts: Dict[tuple, int] = {}
    seq_lookup: Dict[tuple, dict] = {}
    type_dist = {"fact": 0, "grain": 0, "mixed": 0}
    for t in traces:
        chain = t.get("chain", [])
        seq = tuple(_prefixed(s) for s in chain)
        if not seq:
            continue
        types = [s.get("element_type", "unknown") for s in chain]
        arrow = "→".join(types)
        counts[seq] = counts.get(seq, 0) + 1
        seq_lookup[seq] = {"sequence": list(seq), "sequence_type": arrow}
        type_dist[_seq_type(types)] = type_dist.get(_seq_type(types), 0) + 1
    total_chains = sum(counts.values())
    freq = []
    for seq, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
        item = dict(seq_lookup[seq])
        item["occurrence_count"] = cnt
        item["frequency_percent"] = round(cnt / total_chains * 100, 2) if total_chains else 0.0
        freq.append(item)
    if _logger:
        _logger.log(event_type="aggregation_complete",
                    data={"total_traces": len(traces), "unique_sequences": len(counts)})
    return {
        "total_traces": len(traces),
        "total_chains_extracted": total_chains,
        "unique_chain_sequences": len(counts),
        "sequence_frequency": freq,
        "sequence_type_distribution": type_dist,
    }


def extract_chain_steps(traces: list) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    counts: Dict[tuple, int] = {}
    lookup: Dict[tuple, dict] = {}
    trans_dist: Dict[str, int] = {}
    total_steps = 0
    for t in traces:
        chain = t.get("chain", [])
        for a, b in zip(chain, chain[1:]):
            fa, fb = _prefixed(a), _prefixed(b)
            ta = a.get("element_type", "unknown")
            tb = b.get("element_type", "unknown")
            ttype = f"{ta}→{tb}"
            key = (fa, ta, fb, tb)
            counts[key] = counts.get(key, 0) + 1
            lookup[key] = {"from_element": fa, "from_type": ta,
                           "to_element": fb, "to_type": tb,
                           "transition_type": ttype}
            trans_dist[ttype] = trans_dist.get(ttype, 0) + 1
            total_steps += 1
    freq = []
    for key, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
        item = dict(lookup[key])
        item["occurrence_count"] = cnt
        item["frequency_percent"] = round(cnt / total_steps * 100, 2) if total_steps else 0.0
        freq.append(item)
    return {
        "total_traces": len(traces),
        "total_steps_extracted": total_steps,
        "unique_step_types": len(counts),
        "step_frequency": freq,
        "transition_type_distribution": trans_dist,
    }
