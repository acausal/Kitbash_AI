"""conditional_pattern_detector core: association-rule + shallow decision-tree discovery.

Isolation-first tool (see tools/README.md). Allowed imports: stdlib (json,
collections, itertools, math) and Kitbash core's structured_logger (read-only
helper; failed import is non-fatal). Consumes normalized trace objects as emitted
by tools.log_parser (see log_schema.py): each trace has 'chain' (list of steps
with 'element_id'/'element_type'/'traversal_type'/'cartridge'), 'chain_length',
'chain_type', 'session_id'.

Design decisions (user-approved 2026-07-14):
- Decision-tree target is FIXED to 'grain_present_in_chain' (binary, derivable
  from log_parser output). Not user-overridable in v1.
- Condition types NOT derivable from log_parser output are SKIPPED and listed in
  'skipped_types': conditions 'cartridge_crossing', 'session_consistency';
  outcomes 'success_rate', 'cartridge_distribution'. They require trace fields
  (per-step confidence/success, cartridge lists) that query_orchestrator does not
  yet emit (post-1.0 instrumentation).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("conditional_pattern_detector")
except Exception:
    _logger = None

# v1 fixed decision-tree target
DECISION_TARGET = "grain_present_in_chain"

# Derivable condition / outcome types in v1
V1_CONDITION_TYPES = {
    "chain_length", "element_presence", "element_type_distribution",
    "element_count", "traversal_type_pattern",
}
V1_OUTCOME_TYPES = {
    "element_type_distribution", "element_type_sequence",
    "next_element_type", "traversal_type_dominance",
}
# Skipped (documented post-1.0)
SKIPPED_CONDITION_TYPES = ["cartridge_crossing", "session_consistency"]
SKIPPED_OUTCOME_TYPES = ["success_rate", "cartridge_distribution"]


# --------------------------------------------------------------------------- #
# Trace helpers
# --------------------------------------------------------------------------- #
def _norm(t: Any) -> Any:
    """Return the trace dict (unwrap {"trace":..} envelopes or pass dict through)."""
    if isinstance(t, dict):
        if "trace" in t and isinstance(t["trace"], dict) and "chain" in t["trace"]:
            return t["trace"]
        if "chain" in t:
            return t
    return t


def _require_chain(t: Any) -> List[Dict[str, Any]]:
    """Extract 'chain' from a trace; raise ValueError if missing/invalid."""
    trace = _norm(t)
    if not isinstance(trace, dict):
        raise ValueError("trace must be a JSON object")
    chain = trace.get("chain")
    if not isinstance(chain, list):
        raise ValueError("trace missing required field: chain")
    return chain


def _grain_present(t: Any) -> bool:
    return any(step.get("element_type") == "grain" for step in _require_chain(t))


def _extract_features(t: Any) -> Dict[str, Any]:
    """Compute derivable features for a single trace's chain."""
    chain = _require_chain(t)
    length = len(chain)
    types = [s.get("element_type") for s in chain if isinstance(s, dict)]
    facts = sum(1 for ty in types if ty == "fact")
    grains = sum(1 for ty in types if ty == "grain")
    present = {s.get("element_id") for s in chain if isinstance(s, dict) and "element_id" in s}
    ttypes = [s.get("traversal_type") for s in chain if isinstance(s, dict)]
    dom_tt = Counter(ttypes).most_common(1)[0][0] if ttypes else None
    return {
        "length": length,
        "facts": facts,
        "grains": grains,
        "present": present,
        "traversal_types": ttypes,
        "dominant_traversal": dom_tt,
        "sequence": types,  # element_type sequence
    }


# --------------------------------------------------------------------------- #
# Condition matching
# --------------------------------------------------------------------------- #
_VALID_OPS = {">=", "<", "==", "<=", ">"}


def _check_condition(feat: Dict[str, Any], cond: Dict[str, Any]) -> bool:
    """Evaluate a (already-validated) condition dict against precomputed features."""
    ctype = cond["type"]
    if ctype == "chain_length":
        op, val = cond["operator"], cond["value"]
        n = feat["length"]
        if op == ">=": return n >= val
        if op == "<":  return n < val
        if op == "==": return n == val
        if op == "<=": return n <= val
        if op == ">":  return n > val
    if ctype == "element_presence":
        want = cond.get("present", True)
        has = cond["element_id"] in feat["present"]
        return has == want
    if ctype == "element_count":
        op, val = cond["operator"], cond["value"]
        et = cond["element_type"]
        cnt = sum(1 for ty in feat["sequence"] if ty == et)
        if op == ">=": return cnt >= val
        if op == "<":  return cnt < val
        if op == "==": return cnt == val
        if op == "<=": return cnt <= val
        if op == ">":  return cnt > val
    if ctype == "element_type_distribution":
        # matches if fact_percent (of facts+grains) >= value when operator is >=; < and == supported
        total = feat["facts"] + feat["grains"]
        pct = (feat["facts"] / total * 100.0) if total else 0.0
        op, val = cond["operator"], cond["value"]
        if op == ">=": return pct >= val
        if op == "<":  return pct < val
        if op == "==": return pct == val
    if ctype == "traversal_type_pattern":
        return feat["dominant_traversal"] == cond.get("dominant_type")
    raise ValueError(f"unrecognized condition type: {ctype}")


def _validate_condition(cond: Dict[str, Any]) -> None:
    if not isinstance(cond, dict):
        raise ValueError("seed condition must be an object")
    ctype = cond.get("type")
    if ctype is None:
        raise ValueError("seed condition missing 'type'")
    if ctype not in V1_CONDITION_TYPES:
        if ctype in SKIPPED_CONDITION_TYPES:
            raise ValueError(
                f"condition type '{ctype}' not computable in v1 "
                f"(requires extended trace schema; see post-1.0 docs)"
            )
        raise ValueError(f"unrecognized condition type: {ctype}")
    if ctype in ("chain_length", "element_count", "element_type_distribution"):
        if cond.get("operator") not in _VALID_OPS:
            raise ValueError(f"condition {ctype} requires a valid operator")
        if not isinstance(cond.get("value"), (int, float)):
            raise ValueError(f"condition {ctype} requires numeric 'value'")
    if ctype == "element_presence":
        if "element_id" not in cond:
            raise ValueError("element_presence requires 'element_id'")
    if ctype == "traversal_type_pattern":
        if "dominant_type" not in cond:
            raise ValueError("traversal_type_pattern requires 'dominant_type'")


# --------------------------------------------------------------------------- #
# Outcome extraction + metrics
# --------------------------------------------------------------------------- #
def _outcome_distribution(traces: List[Any]) -> Dict[str, Any]:
    """Distribution over derivable outcomes for a set of traces.

    Computes element_type_distribution (fact/grain %), element_type_sequence
    (most common n-gram of element_types), next_element_type (most common type
    following any step), traversal_type_dominance (most common traversal type).
    """
    facts = grains = 0
    sequences: List[Tuple[Any, ...]] = []
    next_counter: Counter = Counter()
    tt_counter: Counter = Counter()
    for tr in traces:
        f = _extract_features(tr)
        facts += f["facts"]; grains += f["grains"]
        seq = f["sequence"]
        if len(seq) >= 2:
            sequences.append(tuple(seq))
        for i in range(len(seq) - 1):
            next_counter[seq[i + 1]] += 1
        for tt in f["traversal_types"]:
            tt_counter[tt] += 1
    total_fg = facts + grains
    fact_pct = round(facts / total_fg * 100.0, 1) if total_fg else 0.0
    grain_pct = round(grains / total_fg * 100.0, 1) if total_fg else 0.0
    # most common sequence (exact element_type n-gram)
    seq_str = Counter("→".join(s) for s in sequences).most_common(1)
    seq_repr = seq_str[0][0] if seq_str else None
    seq_freq_pct = round(seq_str[0][1] / len(sequences) * 100.0, 1) if sequences else 0.0
    next_t = next_counter.most_common(1)
    dom_tt = tt_counter.most_common(1)
    return {
        "element_type_distribution": {
            "fact_percent": fact_pct,
            "grain_percent": grain_pct,
        },
        "element_type_sequence": {
            "sequence": seq_repr,
            "sequence_frequency_percent": seq_freq_pct,
        },
        "next_element_type": {
            "type": next_t[0][0] if next_t else None,
        },
        "traversal_type_dominance": {
            "type": dom_tt[0][0] if dom_tt else None,
        },
    }


def _metrics(matching: List[Any], total: List[Any]) -> Dict[str, Any]:
    """support/confidence/lift/inverse_confidence for the grain target.

    lift = confidence / baseline_rate; baseline_rate=1.0 -> lift=1.0 (guarded).
    """
    support = len(matching)
    baseline = sum(1 for tr in total if _grain_present(tr))
    base_rate = (baseline / len(total)) if total else 0.0
    conf = (sum(1 for tr in matching if _grain_present(tr)) / support) if support else 0.0
    lift = (conf / base_rate) if base_rate > 0 else 1.0
    # inverse: NOT-condition traces
    not_match = [tr for tr in total if tr not in matching]
    inv = (sum(1 for tr in not_match if _grain_present(tr)) / len(not_match)) if not_match else 0.0
    return {
        "support": support,
        "confidence": round(conf, 4),
        "lift": round(lift, 4),
        "inverse_confidence": round(inv, 4),
    }


def _interpret(cond: Dict[str, Any], out: Dict[str, Any], m: Dict[str, Any]) -> str:
    cdesc = cond["type"]
    if cond["type"] == "chain_length":
        cdesc = f"chain length {cond['operator']} {cond['value']}"
    elif cond["type"] == "element_presence":
        cdesc = f"element '{cond['element_id']}' {'present' if cond.get('present', True) else 'absent'}"
    elif cond["type"] == "element_count":
        cdesc = f"{cond['element_type']} count {cond['operator']} {cond['value']}"
    elif cond["type"] == "element_type_distribution":
        cdesc = f"fact% {cond['operator']} {cond['value']}"
    elif cond["type"] == "traversal_type_pattern":
        cdesc = f"dominant traversal = {cond['dominant_type']}"
    dist = out.get("element_type_distribution", {})
    return (f"When {cdesc}, grain present in {round(m['confidence']*100)}% of cases "
            f"(fact:{dist.get('fact_percent')}%, grain:{dist.get('grain_percent')}%, "
            f"lift={m['lift']})")


# --------------------------------------------------------------------------- #
# 1. detect_conditional_patterns
# --------------------------------------------------------------------------- #
def detect_conditional_patterns(traces: list, min_support: int = 2,
                                min_confidence: float = 0.5) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    if min_support < 1:
        raise ValueError("min_support must be >= 1")
    if not (0.0 <= min_confidence <= 1.0):
        raise ValueError("min_confidence must be in [0.0, 1.0]")
    if _logger:
        _logger.log(event_type="detection_started",
                    data={"traces_analyzed": len(traces), "min_support": min_support,
                          "min_confidence": min_confidence})
    # skip traces with empty/invalid chain
    feats: List[Tuple[Any, Dict[str, Any]]] = []
    for t in traces:
        try:
            feats.append((t, _extract_features(t)))
        except (ValueError, KeyError):
            continue  # skip (documented: empty/missing chain)
    valid = [t for t, _ in feats]
    if _logger:
        _logger.log(event_type="detection_progress",
                    data={"traces_with_extractable_conditions": len(valid),
                          "total_traces_analyzed": len(traces)})

    conditions = _generate_conditions(feats)
    rules: List[Dict[str, Any]] = []
    types_found: set = set()
    for cond in conditions:
        matching = [t for t, f in feats if _check_condition(f, cond)]
        if len(matching) < min_support:
            continue
        out = _outcome_distribution(matching)
        m = _metrics(matching, valid)
        if m["confidence"] < min_confidence:
            continue
        types_found.add(cond["type"])
        rules.append({
            "condition": cond,
            "outcome": out,
            "metrics": m,
            "interpretation": _interpret(cond, out, m),
        })

    rules.sort(key=lambda r: (r["metrics"]["confidence"], r["metrics"]["lift"],
                              r["metrics"]["support"]), reverse=True)
    for i, r in enumerate(rules, 1):
        r["rank"] = i

    stats = {
        "total_rules_found": len(rules),
        "rules_after_filtering": len(rules),
        "avg_confidence": round(sum(r["metrics"]["confidence"] for r in rules) / len(rules), 4) if rules else 0.0,
        "avg_support": round(sum(r["metrics"]["support"] for r in rules) / len(rules), 2) if rules else 0,
        "avg_lift": round(sum(r["metrics"]["lift"] for r in rules) / len(rules), 4) if rules else 0.0,
    }
    if _logger:
        _logger.log(event_type="detection_complete",
                    data={"patterns_found": len(rules),
                          "patterns_after_filtering": len(rules)})
    return {
        "detection_params": {
            "min_support": min_support,
            "min_confidence": min_confidence,
            "total_traces_analyzed": len(traces),
            "traces_with_extractable_conditions": len(valid),
        },
        "statistics": stats,
        "rules": rules,
        "condition_types_found": sorted(types_found),
        "skipped_types": {
            "conditions": SKIPPED_CONDITION_TYPES,
            "outcomes": SKIPPED_OUTCOME_TYPES,
        },
    }


def _generate_conditions(feats: List[Tuple[Any, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Auto-generate candidate conditions from trace structure (quality over quantity)."""
    conditions: List[Dict[str, Any]] = []
    lengths = [f["length"] for _, f in feats]
    if lengths:
        for v in sorted(set(lengths)):
            conditions.append({"type": "chain_length", "operator": ">=", "value": v})
    # top-N most common element ids -> presence
    present_counter: Counter = Counter()
    for _, f in feats:
        present_counter.update(f["present"])
    for eid, _ in present_counter.most_common(10):
        conditions.append({"type": "element_presence", "element_id": eid, "present": True})
    # element_type_distribution thresholds
    for pct in (50, 60, 70, 80):
        conditions.append({"type": "element_type_distribution", "operator": ">=", "value": pct})
    # element_count for fact/grain
    for et in ("fact", "grain"):
        counts = [sum(1 for ty in f["sequence"] if ty == et) for _, f in feats]
        for v in sorted(set(c for c in counts if c > 0)):
            conditions.append({"type": "element_count", "element_type": et,
                               "operator": ">=", "value": v})
    # traversal_type_pattern: dominant types
    tt_counter: Counter = Counter()
    for _, f in feats:
        if f["dominant_traversal"]:
            tt_counter[f["dominant_traversal"]] += 1
    for tt, _ in tt_counter.most_common(5):
        conditions.append({"type": "traversal_type_pattern", "dominant_type": tt})
    return conditions


# --------------------------------------------------------------------------- #
# 2. detect_seeded_patterns
# --------------------------------------------------------------------------- #
def detect_seeded_patterns(traces: list, seed_conditions: list,
                           min_support: int = 2) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    if not isinstance(seed_conditions, list) or not seed_conditions:
        raise ValueError("seed_conditions must be a non-empty list")
    if min_support < 1:
        raise ValueError("min_support must be >= 1")
    for cond in seed_conditions:
        _validate_condition(cond)
    feats = [(t, _extract_features(t)) for t in traces
             if isinstance(t, dict) and _safe_chain(t)]
    valid = [t for t, _ in feats]
    results = []
    for cond in seed_conditions:
        matching = [t for t, f in feats if _check_condition(f, cond)]
        out = _outcome_distribution(matching) if matching else _outcome_distribution([])
        m = _metrics(matching, valid)
        results.append({
            "seed_condition": cond,
            "traces_matching_condition": len(matching),
            "outcomes": [{
                "outcome": out,
                "support": m["support"],
                "confidence": m["confidence"],
                "lift": m["lift"],
            }],
        })
    if _logger:
        _logger.log(event_type="detection_complete",
                    data={"seed_conditions_provided": len(seed_conditions)})
    return {
        "seeded_params": {
            "seed_conditions_provided": len(seed_conditions),
            "min_support": min_support,
            "total_traces_analyzed": len(traces),
        },
        "results": results,
        "skipped_types": {
            "conditions": SKIPPED_CONDITION_TYPES,
            "outcomes": SKIPPED_OUTCOME_TYPES,
        },
    }


def _safe_chain(t: Any) -> bool:
    try:
        _require_chain(t)
        return True
    except (ValueError, KeyError):
        return False


# --------------------------------------------------------------------------- #
# 3. extract_decision_trees
# --------------------------------------------------------------------------- #
def _entropy(traces: List[Any]) -> float:
    n = len(traces)
    if n == 0:
        return 0.0
    p = sum(1 for tr in traces if _grain_present(tr)) / n
    if p in (0.0, 1.0):
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _candidate_splits(feats: List[Tuple[Any, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    splits = []
    lengths = sorted({f["length"] for _, f in feats})
    for v in lengths:
        splits.append({"type": "chain_length", "operator": ">=", "value": v})
    present_counter: Counter = Counter()
    for _, f in feats:
        present_counter.update(f["present"])
    for eid, _ in present_counter.most_common(8):
        splits.append({"type": "element_presence", "element_id": eid, "present": True})
    for pct in (50, 60, 70, 80):
        splits.append({"type": "element_type_distribution", "operator": ">=", "value": pct})
    tt_counter: Counter = Counter()
    for _, f in feats:
        if f["dominant_traversal"]:
            tt_counter[f["dominant_traversal"]] += 1
    for tt, _ in tt_counter.most_common(4):
        splits.append({"type": "traversal_type_pattern", "dominant_type": tt})
    return splits


def _best_split(traces: List[Any], feats: Dict[Any, Dict[str, Any]], depth_remaining: int) -> Optional[Dict[str, Any]]:
    if depth_remaining <= 0 or not traces:
        return None
    parent_h = _entropy(traces)
    if parent_h == 0.0:
        return None  # pure node, no split
    best = None
    best_gain = 0.0
    for cond in _candidate_splits(list(feats.items())):
        true_set, false_set = [], []
        for t in traces:
            (true_set if _check_condition(feats[id(t)], cond) else false_set).append(t)
        if not true_set or not false_set:
            continue
        w = len(true_set) / len(traces)
        child_h = w * _entropy(true_set) + (1 - w) * _entropy(false_set)
        gain = parent_h - child_h
        if gain > best_gain:
            best_gain = gain
            best = (cond, true_set, false_set)
    if best is None:
        return None
    cond, true_set, false_set = best
    node: Dict[str, Any] = {
        "condition": cond,
        "info_gain": round(best_gain, 4),
        "traces_true": len(true_set),
        "traces_false": len(false_set),
    }
    if depth_remaining - 1 > 0:
        child_true = _best_split(true_set, feats, depth_remaining - 1)
        child_false = _best_split(false_set, feats, depth_remaining - 1)
        children: Dict[str, Any] = {}
        if child_true:
            children["true"] = child_true
        else:
            children["true"] = {
                "condition": {"type": "leaf", "value": "grain_present" if any(_grain_present(t) for t in true_set) else "grain_absent"},
                "info_gain": 0.0, "traces_true": len(true_set), "traces_false": 0,
                "outcome_distribution": _target_dist(true_set),
            }
        if child_false:
            children["false"] = child_false
        else:
            children["false"] = {
                "condition": {"type": "leaf", "value": "grain_present" if any(_grain_present(t) for t in false_set) else "grain_absent"},
                "info_gain": 0.0, "traces_true": len(false_set), "traces_false": 0,
                "outcome_distribution": _target_dist(false_set),
            }
        node["children"] = children
    else:
        node["outcome_distribution"] = {
            "true_branch_grain_present": sum(1 for t in true_set if _grain_present(t)),
            "false_branch_grain_present": sum(1 for t in false_set if _grain_present(t)),
        }
    return node


def _target_dist(traces: List[Any]) -> Dict[str, int]:
    return {
        "grain_present": sum(1 for t in traces if _grain_present(t)),
        "grain_absent": sum(1 for t in traces if not _grain_present(t)),
    }


def extract_decision_trees(traces: list, depth: int = 2) -> dict:
    if not isinstance(traces, list):
        raise ValueError("traces must be a list")
    if depth < 0:
        raise ValueError("depth must be >= 0")
    if depth > 10:
        raise ValueError("depth must be <= 10")
    feats = {id(t): _extract_features(t) for t in traces if isinstance(t, dict) and _safe_chain(t)}
    valid = list(feats.keys())
    if not valid:
        root = {
            "condition": {"type": "leaf", "value": "no_traces"},
            "info_gain": 0.0, "traces_true": 0, "traces_false": 0,
            "outcome_distribution": {"grain_present": 0, "grain_absent": 0},
        }
        return {"tree_params": {"depth": depth, "total_traces": len(traces),
                                "target": DECISION_TARGET},
                "decision_tree": {"root": root}}
    valid_traces = [t for t in traces if id(t) in feats]
    root = _best_split(valid_traces, feats, depth)
    if root is None:
        root = {
            "condition": {"type": "leaf", "value": "no_split"},
            "info_gain": 0.0,
            "traces_true": len(valid_traces),
            "traces_false": 0,
            "outcome_distribution": _target_dist(valid_traces),
        }
    if _logger:
        _logger.log(event_type="detection_complete",
                    data={"tree_depth": depth, "target": DECISION_TARGET})
    return {
        "tree_params": {
            "depth": depth,
            "total_traces": len(traces),
            "target": DECISION_TARGET,
            "target_description": "binary split on whether the chain contains a 'grain' step (derivable from log_parser output)",
        },
        "decision_tree": {"root": root},
        "skipped_types": {
            "conditions": SKIPPED_CONDITION_TYPES,
            "outcomes": SKIPPED_OUTCOME_TYPES,
        },
    }


# --------------------------------------------------------------------------- #
# 4. filter_patterns
# --------------------------------------------------------------------------- #
def filter_patterns(patterns: list, min_confidence: float, min_lift: float = 1.0) -> dict:
    if not isinstance(patterns, list):
        raise ValueError("patterns must be a list")
    if not (0.0 <= min_confidence <= 1.0):
        raise ValueError("min_confidence must be in [0.0, 1.0]")
    if min_lift < 0.0:
        raise ValueError("min_lift must be >= 0.0")
    kept = []
    for p in patterns:
        m = p.get("metrics", {})
        if m.get("confidence", 0) >= min_confidence and m.get("lift", 0) >= min_lift:
            kept.append(p)
    kept.sort(key=lambda r: (r["metrics"]["confidence"], r["metrics"]["lift"]), reverse=True)
    for i, r in enumerate(kept, 1):
        if "rank" in r:
            r["rank"] = i
    if _logger:
        _logger.log(event_type="filtering_complete",
                    data={"patterns_after_filtering": len(kept)})
    return {
        "filter_criteria": {"min_confidence": min_confidence, "min_lift": min_lift},
        "total_patterns_input": len(patterns),
        "patterns_after_filtering": len(kept),
        "filtered_out": len(patterns) - len(kept),
        "patterns": kept,
    }


# --------------------------------------------------------------------------- #
# 5. rank_patterns_by_metric
# --------------------------------------------------------------------------- #
def rank_patterns_by_metric(patterns: list, metric: str = "confidence") -> dict:
    if not isinstance(patterns, list):
        raise ValueError("patterns must be a list")
    if metric not in ("confidence", "lift", "support"):
        raise ValueError(f"invalid metric: {metric!r} (expected confidence/lift/support)")
    ranked = sorted(patterns, key=lambda p: p.get("metrics", {}).get(metric, 0), reverse=True)
    out = []
    for i, p in enumerate(ranked, 1):
        rp = dict(p)
        rp["rank"] = i
        out.append(rp)
    if _logger:
        _logger.log(event_type="ranking_complete", data={"metric": metric, "count": len(out)})
    return {"metric": metric, "ranked_patterns": out}
