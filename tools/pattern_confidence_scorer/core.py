"""pattern_confidence_scorer core: score discovered patterns vs. outcomes.

Stdlib only (json, collections, math, datetime). Isolation-first tool (see
tools/README.md). Consumes/returns JSON-serializable dicts.

Error taxonomy (matches the SPEC CLI exit codes):
  ValueError   -> invalid pattern_type / empty traces / bad decay params  (CLI 1)
  FileNotFoundError -> dream_bucket/traces file missing                  (CLI 2)
  OSError/RuntimeError -> file IO / matching failure                    (CLI 2/3)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import pattern_matching as M
from . import metrics as MET

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("pattern_confidence_scorer")
except Exception:
    _logger = None


def _log(event: str, **data) -> None:
    if _logger:
        try:
            _logger.log(event_type=event, data=data)
        except Exception:
            pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_one(pattern: Dict, observations: List[Dict],
               pattern_type: str) -> Dict[str, Any]:
    cm = M.build_confusion(pattern, observations, pattern_type)
    m = MET.compute_metrics(cm)
    flag = MET.confidence_flag(m, m["support"])
    # Capture per-observation decay metadata (used by decay_confidence_by_age).
    decay_obs = []
    if pattern_type == "collision":
        pair = pattern.get("collision_pair", [])
        for obs in observations:
            fires = M.collision_fires(pair, obs)
            exact = (obs.get("returned_id") == pair[0] and obs.get("correct_id") == pair[1]) if len(pair) >= 2 else False
            correct = fires and exact
            decay_obs.append({"ts": obs.get("timestamp"), "fired": fires,
                              "correct": correct})
    else:
        if pattern_type == "grain_chain":
            pat_seq = pattern.get("sequence", pattern.get("grains", []))
        else:
            pat_seq = pattern.get("sequence", [])
        for obs in observations:
            seq = obs.get("sequence", obs.get("grain_sequence", []))
            fires = M.sequence_fires(pat_seq, seq)
            correct = M._is_correct(obs.get("outcome", "success"))
            decay_obs.append({"ts": obs.get("timestamp"), "fired": fires,
                              "correct": correct})
    dates = [d["ts"] for d in decay_obs if d.get("ts")]
    obs_dates = {"newest": max(dates), "oldest": min(dates)} if dates else {}
    return {
        "pattern_id": pattern.get("pattern_id", ""),
        "pattern": pattern.get("sequence", pattern.get("collision_pair",
                                                        pattern.get("grains", []))),
        "pattern_frequency_in_data": m["support"],
        "metrics": m,
        "interpretation": {
            "reliability": MET.reliability_level(m["f1_score"]),
            "confidence_flag": flag,
            "sample_size_note": MET.sample_size_note(m["support"]),
        },
        "details": {
            "true_positives": cm.tp,
            "false_positives": cm.fp,
            "true_negatives": cm.tn,
            "false_negatives": cm.fn,
            "total_observations": cm.total,
        },
        "observation_dates": obs_dates,
        "_decay_obs": decay_obs,
    }


def _aggregate(scores: List[Dict]) -> Dict[str, Any]:
    if not scores:
        return {
            "mean_precision": 0.0, "mean_recall": 0.0, "mean_f1": 0.0,
            "patterns_with_high_confidence": 0,
            "patterns_with_low_sample_size": 0,
            "patterns_with_low_reliability": 0,
        }
    n = len(scores)
    mp = sum(s["metrics"]["precision"] for s in scores) / n
    mr = sum(s["metrics"]["recall"] for s in scores) / n
    mf = sum(s["metrics"]["f1_score"] for s in scores) / n
    return {
        "mean_precision": round(mp, 4),
        "mean_recall": round(mr, 4),
        "mean_f1": round(mf, 4),
        "patterns_with_high_confidence": sum(
            1 for s in scores if s["interpretation"]["reliability"] == "high"),
        "patterns_with_low_sample_size": sum(
            1 for s in scores if s["interpretation"]["confidence_flag"] == "low_sample_size"),
        "patterns_with_low_reliability": sum(
            1 for s in scores if s["interpretation"]["reliability"] == "low"),
    }


_VALID_TYPES = ("sequence", "collision", "grain_chain")


# --------------------------------------------------------------------------- #
# 1. score_patterns_against_traces
# --------------------------------------------------------------------------- #
def score_patterns_against_traces(patterns: List[Dict], traces: List[Dict],
                                  pattern_type: str = "sequence") -> dict:
    if pattern_type not in _VALID_TYPES:
        raise ValueError(f"unknown pattern_type: {pattern_type!r} "
                         f"(expected one of {_VALID_TYPES})")
    if not traces:
        raise ValueError("traces list is empty")
    _log("score_started", pattern_type=pattern_type, n_patterns=len(patterns))
    scores = [_score_one(p, traces, pattern_type) for p in patterns]
    result = {
        "scoring_params": {
            "pattern_type": pattern_type,
            "total_patterns_scored": len(patterns),
            "total_traces_used": len(traces),
            "timestamp_generated": _now_iso(),
        },
        "pattern_scores": scores,
        "aggregate_statistics": _aggregate(scores),
    }
    _log("score_complete", n_scores=len(scores))
    return result


# --------------------------------------------------------------------------- #
# 2. score_patterns_against_dream_bucket
# --------------------------------------------------------------------------- #
def _read_jsonl(path: str) -> List[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed JSONL in {path!r}: {e}")
    except OSError as e:
        raise OSError(f"failed to read {path!r}: {e}")


def score_patterns_against_dream_bucket(patterns: List[Dict],
                                        dream_bucket_file: str,
                                        pattern_type: str = "sequence") -> dict:
    if pattern_type not in _VALID_TYPES:
        raise ValueError(f"unknown pattern_type: {pattern_type!r}")
    obs = _read_jsonl(dream_bucket_file)
    types = sorted({o.get("type", "unknown") for o in obs})
    scores = [_score_one(p, obs, pattern_type) for p in patterns]
    return {
        "scoring_params": {
            "pattern_type": pattern_type,
            "total_patterns_scored": len(patterns),
            "total_observations_used": len(obs),
            "observation_types": types,
            "timestamp_generated": _now_iso(),
        },
        "pattern_scores": scores,
        "aggregate_statistics": {
            "mean_precision": _aggregate(scores)["mean_precision"],
            "mean_recall": _aggregate(scores)["mean_recall"],
            "patterns_explaining_observations": sum(
                1 for s in scores if s["metrics"]["support"] > 0),
            "unexplained_observations": sum(
                1 for o in obs if not any(
                    M.build_confusion(p, [o], pattern_type).tp > 0
                    for p in patterns)),
        },
    }


# --------------------------------------------------------------------------- #
# 3. compare_pattern_reliability
# --------------------------------------------------------------------------- #
def compare_pattern_reliability(patterns: List[Dict], traces_file: str = None,
                               dream_bucket_file: str = None,
                               pattern_type: str = "sequence") -> dict:
    if traces_file is None and dream_bucket_file is None:
        raise ValueError("provide at least one of traces_file / dream_bucket_file")
    methods = []
    scores_traces = None
    scores_db = None
    if traces_file is not None:
        methods.append("traces")
        traces = _read_jsonl(traces_file) if traces_file.endswith(".jsonl") \
            else json.load(open(traces_file, encoding="utf-8"))
        scores_traces = score_patterns_against_traces(patterns, traces, pattern_type)
    if dream_bucket_file is not None:
        methods.append("dream_bucket")
        scores_db = score_patterns_against_dream_bucket(
            patterns, dream_bucket_file, pattern_type)

    divergences = []
    consistent = divergent = 0
    if scores_traces is not None and scores_db is not None:
        by_id_t = {s["pattern_id"]: s for s in scores_traces["pattern_scores"]}
        by_id_d = {s["pattern_id"]: s for s in scores_db["pattern_scores"]}
        for pid in set(by_id_t) & set(by_id_d):
            d = abs(by_id_t[pid]["metrics"]["f1_score"]
                    - by_id_d[pid]["metrics"]["f1_score"])
            divergences.append(d)
            if d > 0.25:
                divergent += 1
            else:
                consistent += 1
    mean_div = round(sum(divergences) / len(divergences), 4) if divergences else 0.0
    result = {
        "comparison": {
            "scoring_methods": methods,
            "timestamp_generated": _now_iso(),
        },
        "scores_from_traces": scores_traces,
        "scores_from_dream_bucket": scores_db,
        "agreement_analysis": {
            "patterns_with_consistent_scores": consistent,
            "patterns_with_divergent_scores": divergent,
            "mean_score_divergence": mean_div,
            "note": ("High agreement suggests robust scoring across data sources"
                     if mean_div <= 0.1 else
                     "Divergence suggests possible data quality issues"),
        },
    }
    return result


# --------------------------------------------------------------------------- #
# 4. decay_confidence_by_age
# --------------------------------------------------------------------------- #
def decay_confidence_by_age(pattern_scores: dict, decay_factor: float = 0.99,
                            reference_date: str = None) -> dict:
    if not (0.0 <= decay_factor <= 1.0):
        raise ValueError(f"decay_factor must be in [0,1], got {decay_factor}")
    ref = None
    if reference_date is not None:
        try:
            ref = datetime.strptime(reference_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"invalid reference_date (need YYYY-MM-DD): {reference_date!r}")
    else:
        ref = datetime.now(timezone.utc).date()

    decayed = []
    for s in pattern_scores.get("pattern_scores", []):
        obs = s.get("_decay_obs", [])
        wtp = wfp = wtn = wfn = 0.0
        ages = []
        for o in obs:
            ts = o.get("ts")
            if not ts:
                age = 0
            else:
                d = datetime.strptime(ts[:10], "%Y-%m-%d").date()
                age = max((ref - d).days, 0)
            ages.append(age)
            w = decay_factor ** age
            if o["fired"] and o["correct"]:
                wtp += w
            elif o["fired"] and not o["correct"]:
                wfp += w
            elif (not o["fired"]) and o["correct"]:
                wtn += w
            else:
                wfn += w
        # weighted confusion -> decayed metrics
        precision = (wtp / (wtp + wfp)) if (wtp + wfp) else 0.0
        recall = (wtp / (wtp + wfn)) if (wtp + wfn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              ) if (precision + recall) else 0.0
        min_age = max(ages) if ages else 0
        min_weight = decay_factor ** min_age
        decayed.append({
            "pattern_id": s["pattern_id"],
            "original_precision": s["metrics"]["precision"],
            "original_recall": s["metrics"]["recall"],
            "original_f1": s["metrics"]["f1_score"],
            "decayed_precision": round(precision, 4),
            "decayed_recall": round(recall, 4),
            "decayed_f1": round(f1, 4),
            "age_weight": round(min_weight, 4),
            "oldest_age_days": min_age,
            "observation_dates": s.get("observation_dates", {}),
        })
    return {
        "decay_params": {
            "decay_factor": decay_factor,
            "reference_date": ref.isoformat(),
            "oldest_observation_age_days": max(
                (d.get("oldest_age_days", 0) for d in decayed), default=0),
        },
        "decayed_pattern_scores": decayed,
    }
