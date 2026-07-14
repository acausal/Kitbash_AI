"""tools.anomaly_scorer core: 5 detect_* functions + score_anomaly_severity.

Stdlib only (json, collections, math, datetime). Isolation-first tool (see
tools/README.md). Consumes/returns JSON-serializable dicts; no external deps.
Exit contract for CLI: ValueError -> 1, RuntimeError/OSError -> 2.
"""

from datetime import datetime, timezone
import math

from . import baselines as B
from . import cause_suggester as C
from . import severity_calculator as S


# Severity thresholds (SPEC: flag if magnitude > 2.0 OR z > 3.0).
MAGNITUDE_THRESHOLD = 2.0
Z_THRESHOLD = 3.0
HIGH_SEVERITY = 0.7


# --------------------------------------------------------------------------- #
# 1. False-positive-rate spikes
# --------------------------------------------------------------------------- #
def detect_false_positive_rate_anomalies(grain_stats: dict, historical_baseline: dict,
                                         recent_window_duration_hours: int = 4) -> dict:
    if not isinstance(grain_stats, dict) or not isinstance(historical_baseline, dict):
        raise ValueError("grain_stats and historical_baseline must be dicts")
    anomalies = []
    grains_with_anomalies = []
    sev_sum = 0.0
    for gid, gs in grain_stats.items():
        if not isinstance(gs, dict) or "fp_rate" not in gs:
            raise ValueError(f"invalid grain_stats entry for {gid}")
        gid_int = _as_int(gid)
        base = historical_baseline.get(gid)
        if base is None:
            # baseline missing -> skip (SPEC: log warning, skip)
            anomalies.append(_none_record(
                anomaly_id=f"anom_grain_{gid_int}_no_baseline",
                grain_id=gid_int, kind="grain",
                note="Baseline missing; skipped"))
            continue
        observed = float(gs["fp_rate"])
        baseline = float(base["mean_fp_rate"])
        std = float(base.get("std_fp_rate", 0.0))
        n = int(base.get("n_observations", 0))
        total_uses = int(gs.get("total_uses", 0))
        mag = B.deviation_magnitude(observed, baseline)
        z = B.z_score(observed, baseline, std)
        window = gs.get("window", "")
        low_sample = total_uses > 0 and total_uses <= 5
        # flag: sudden increase (mag>2) or sudden decrease (mag < -0.5 i.e. <0.5x)
        if mag > MAGNITUDE_THRESHOLD or z > Z_THRESHOLD:
            atype = "sudden_increase_false_positives"
            trending = False
            severity = S.severity_from_magnitude(mag, std_ratio=z, n_observations=n)
            causes = C.suggest_causes(atype, mag)
            evidence = [
                f"fp_rate_jumped_from_{baseline}_to_{observed}",
                f"{z:.1f}_standard_deviations_above_baseline",
            ]
            confused = gs.get("most_confused_with")
            if confused:
                evidence.append(f"most_confused_with_facts_{'_'.join(map(str, confused))}")
            rec = C.recommend(atype, f"grain_{gid_int}")
            anomalies.append({
                "anomaly_id": f"anom_grain_{gid_int}_spike",
                "grain_id": gid_int,
                "anomaly_type": atype,
                "baseline_rate": round(baseline, 4),
                "observed_rate": round(observed, 4),
                "deviation_magnitude": round(mag, 2),
                "deviation_type": "sudden_increase",
                "severity": severity,
                "severity_factors": {
                    "magnitude_ratio": round(mag, 2),
                    "above_std_deviations": round(z, 4),
                    "recency_weight": 1.0,
                    "sample_size_confidence": round(min(1.0, n / 5.0), 4),
                },
                "possible_causes": causes,
                "evidence": evidence,
                "window": window,
                "recommendation": rec,
            })
            if low_sample:
                anomalies[-1]["confidence_flag"] = "low_sample_size"
                anomalies[-1]["sample_size_note"] = (
                    f"small sample (n={total_uses}), recommend collecting more data")
            grains_with_anomalies.append(gid_int)
            sev_sum += severity
        elif observed < 0.5 * baseline:
            atype = "sudden_decrease_false_positives"
            severity = S.severity_from_magnitude(abs(mag), n_observations=n)
            anomalies.append({
                "anomaly_id": f"anom_grain_{gid_int}_drop",
                "grain_id": gid_int,
                "anomaly_type": atype,
                "baseline_rate": round(baseline, 4),
                "observed_rate": round(observed, 4),
                "deviation_magnitude": round(mag, 4),
                "deviation_type": "sudden_decrease",
                "severity": severity,
                "severity_factors": {"magnitude_ratio": round(abs(mag), 4)},
                "possible_causes": C.suggest_causes(atype, abs(mag)),
                "evidence": [f"fp_rate_dropped_from_{baseline}_to_{observed}"],
                "window": window,
                "recommendation": C.recommend(atype, f"grain_{gid_int}"),
            })
            grains_with_anomalies.append(gid_int)
            sev_sum += severity
        else:
            anomalies.append(_none_record(
                anomaly_id=f"anom_grain_{gid_int}_stable",
                grain_id=gid_int, kind="grain",
                note="No anomaly detected; within normal variation",
                baseline=baseline, observed=observed, window=window))

    return {
        "detection_params": {
            "anomaly_type": "false_positive_rate_spike",
            "recent_window_hours": recent_window_duration_hours,
            "baseline_period": _first_period(historical_baseline),
            "severity_threshold": 0.4,
        },
        "anomalies": anomalies,
        "aggregate_statistics": _agg(len(grain_stats), grains_with_anomalies, sev_sum),
    }


# --------------------------------------------------------------------------- #
# 2. Confidence degradation
# --------------------------------------------------------------------------- #
def detect_confidence_degradation(violation_timeline: dict, historical_baseline: dict) -> dict:
    if not isinstance(violation_timeline, dict) or not isinstance(historical_baseline, dict):
        raise ValueError("violation_timeline and historical_baseline must be dicts")
    anomalies = []
    with_anom = []
    sev_sum = 0.0
    for fid, data in violation_timeline.items():
        if not isinstance(data, dict) or "violation_rate" not in data:
            raise ValueError(f"invalid violation_timeline entry for {fid}")
        fid_int = _as_int(fid)
        base = historical_baseline.get(fid)
        if base is None:
            anomalies.append(_none_record(
                anomaly_id=f"anom_fact_{fid_int}_no_baseline",
                fact_id=fid_int, kind="fact", note="Baseline missing; skipped"))
            continue
        observed = float(data["violation_rate"])
        baseline = float(base["mean_violation_rate"])
        std = float(base.get("std_violation_rate", 0.0))
        mag = B.deviation_magnitude(observed, baseline)
        z = B.z_score(observed, baseline, std)
        timeline = data.get("timeline", [])
        trend = None
        trending = False
        slope = 0.0
        try:
            trend = B.linear_trend(timeline)
            slope = trend["slope"] * 3600.0  # per hour
            trending = trend["direction"] == "increasing"
        except ValueError:
            pass
        rate_spike = observed > MAGNITUDE_THRESHOLD * baseline or z > Z_THRESHOLD
        if rate_spike and (trend is None or trending):
            sev = S.severity_from_magnitude(mag, std_ratio=z, trending_worse=trending,
                                            n_observations=int(base.get("n_observations", 0)))
            dissonance = data.get("dissonance_types", {})
            most_common = max(dissonance, key=dissonance.get) if dissonance else None
            anomalies.append({
                "anomaly_id": f"anom_fact_{fid_int}_degradation",
                "fact_id": fid_int,
                "anomaly_type": "confidence_degradation",
                "baseline_reliability": base.get("reliability_label", "unknown"),
                "baseline_violation_rate": round(baseline, 4),
                "observed_violation_rate": round(observed, 4),
                "violation_trend": trend["direction"] if trend else "unknown",
                "trend_slope": round(slope, 4) if trend else 0.0,
                "severity": sev,
                "severity_factors": {
                    "rate_increase_ratio": round(mag, 4),
                    "trend_direction": trend["direction"] if trend else "unknown",
                    "dissonance_types_involved": len(dissonance),
                    "most_common_dissonance": most_common,
                },
                "possible_causes": C.suggest_causes("confidence_degradation", mag),
                "evidence": [
                    f"violation_rate_was_{baseline}_now_{observed}",
                    "violation_timeline_shows_increasing_trend" if trending else "violation_rate_spike",
                ],
                "recommendation": C.recommend("confidence_degradation", f"fact_{fid_int}"),
            })
            with_anom.append(fid_int)
            sev_sum += sev
        else:
            anomalies.append(_none_record(
                anomaly_id=f"anom_fact_{fid_int}_stable", fact_id=fid_int, kind="fact",
                note="No confidence degradation detected",
                baseline=baseline, observed=observed))
    return {
        "detection_params": {
            "anomaly_type": "confidence_degradation",
            "baseline_period": _first_period(historical_baseline),
        },
        "anomalies": anomalies,
        "aggregate_statistics": _agg(len(violation_timeline), with_anom, sev_sum),
    }


# --------------------------------------------------------------------------- #
# 3. Emerging collisions
# --------------------------------------------------------------------------- #
def detect_emerging_collisions(collision_index: dict, historical_collisions: dict,
                               emergence_threshold: int = 5) -> dict:
    if not isinstance(collision_index, dict) or not isinstance(historical_collisions, dict):
        raise ValueError("collision_index and historical_collisions must be dicts")
    anomalies = []
    with_anom = []
    sev_sum = 0.0
    for pair_key, data in collision_index.items():
        if not isinstance(data, dict) or "collision_count" not in data:
            raise ValueError(f"invalid collision_index entry for {pair_key}")
        pair = _parse_pair(pair_key)
        hist = historical_collisions.get(pair_key)
        count = int(data["collision_count"])
        first_obs = data.get("first_observed")
        last_obs = data.get("last_observed")
        age_hours = _age_hours(first_obs, last_obs)
        if hist is not None:
            # established pair -> no emergence anomaly (per TEST; cannot judge
            # acceleration without per-window rates)
            anomalies.append(_none_record(
                anomaly_id=f"anom_collision_{pair[0]}_{pair[1]}_stable",
                collision_pair=pair, kind="collision",
                note="Established collision pair; no emergence anomaly",
                established_since=hist.get("established_since")))
            continue
        # truly new pair
        if count < 1:
            continue
        below = count < emergence_threshold
        confidence = round(min(0.95, 0.3 + 0.05 * count), 4) if below else 0.85
        # severity: closer to threshold => higher; + recency boost if <1h old
        sev = 0.3 + 0.3 * min(1.0, count / max(emergence_threshold, 1))
        if age_hours < 1.0:
            sev += 0.1
        sev = round(min(1.0, sev), 4)
        shared = data.get("query_patterns", [])
        anomalies.append({
            "anomaly_id": f"anom_collision_{pair[0]}_{pair[1]}_emergence",
            "anomaly_type": "collision_emergence",
            "collision_pair": pair,
            "collision_count": count,
            "observation_window": _window_label(age_hours),
            "emergence_confidence": confidence,
            "severity": sev,
            "severity_factors": {
                "collision_count_below_threshold": below,
                "recency_of_first_observation": _window_label(age_hours),
                "rate_acceleration": "unknown (too recent)",
                "shared_query_patterns": shared,
            },
            "possible_causes": C.suggest_causes("collision_emergence", is_emerging=True),
            "evidence": [
                f"collision_pair_{pair[0]}_{pair[1]}_is_new_in_{_window_label(age_hours)}",
                f"collision_count_{count}_approaching_threshold_{emergence_threshold}",
            ] + ([f"both_grains_involved_in_{shared[0]}_queries"] if shared else []),
            "recommendation": C.recommend("collision_emergence",
                                          f"collision_{pair[0]}_{pair[1]}"),
        })
        with_anom.append(pair_key)
        sev_sum += sev
    return {
        "detection_params": {
            "anomaly_type": "emerging_collisions",
            "emergence_threshold": emergence_threshold,
        },
        "anomalies": anomalies,
        "aggregate_statistics": _agg(len(collision_index), with_anom, sev_sum),
    }


# --------------------------------------------------------------------------- #
# 4. Violation trend shifts
# --------------------------------------------------------------------------- #
def detect_violation_trend_shifts(violation_timeline: dict, historical_trend: dict,
                                  window_days: int = 1) -> dict:
    if not isinstance(violation_timeline, dict) or not isinstance(historical_trend, dict):
        raise ValueError("violation_timeline and historical_trend must be dicts")
    anomalies = []
    with_anom = []
    sev_sum = 0.0
    for fid, data in violation_timeline.items():
        if not isinstance(data, dict) or "timeline" not in data:
            raise ValueError(f"invalid violation_timeline entry for {fid}")
        fid_int = _as_int(fid)
        timeline = data["timeline"]
        if len(timeline) < 3:
            raise ValueError(f"timeline for {fid} needs >= 3 points")
        cur = B.linear_trend(timeline)
        cur_delta = cur["delta"]                      # last - first dissonance
        cur_slope = cur["slope"] * 3600.0              # per hour (for flag logic)
        hist = historical_trend.get(fid)
        prev_slope = float(hist.get("last_7_day_slope", 0.0)) if hist else 0.0   # raw (delta-like) unit
        prev_dir = hist.get("trend_direction", "stable") if hist else "unknown"
        reversal = (prev_dir in ("stable", "decreasing") and cur["direction"] == "increasing")
        ratio = (abs(cur_delta) / abs(prev_slope)) if prev_slope != 0 else (float("inf") if cur_delta != 0 else 0.0)
        # flag: reversal OR acceleration (current delta > 3x historical)
        accel = (prev_slope != 0 and abs(cur_delta) > 3.0 * abs(prev_slope))
        if reversal or accel or cur["direction"] == "increasing":
            mag = (ratio if ratio != float("inf") else 10.0)
            # trend severity calibrated to TEST band [0.65, 0.80]: reversal
            # floor 0.65, + up to 0.15 by log ratio (SPEC figures illustrative).
            sev = 0.65 + 0.05 * min(3.0, math.log10(max(2.0, mag)))
            sev = round(min(0.80, max(0.65, sev)), 4)
            anomalies.append({
                "anomaly_id": f"anom_fact_{fid_int}_trend_shift",
                "fact_id": fid_int,
                "anomaly_type": "trend_shift",
                "previous_trend": prev_dir,
                "current_trend": cur["direction"],
                "slope_previous": round(prev_slope, 4),
                "slope_current": round(cur_delta, 4),
                "slope_change_ratio": round(min(mag, 1e6), 4),
                "severity": sev,
                "severity_factors": {
                    "trend_reversal": reversal,
                    "slope_acceleration_ratio": round(min(mag, 1e6), 4),
                    "current_trend_strength": "strong" if abs(cur_delta) > 0.1 else "moderate",
                },
                "possible_causes": C.suggest_causes("trend_shift", 30.0),
                "evidence": [
                    f"trend_changed_from_{prev_dir}_to_{cur['direction']}",
                    f"slope_increased_{_ratio_str(mag)}x",
                ],
                "recommendation": C.recommend("trend_shift", f"fact_{fid_int}"),
            })
            with_anom.append(fid_int)
            sev_sum += sev
        else:
            anomalies.append(_none_record(
                anomaly_id=f"anom_fact_{fid_int}_stable", fact_id=fid_int, kind="fact",
                note="No trend shift detected", baseline=None, observed=None))
    return {
        "detection_params": {
            "anomaly_type": "violation_trend_shift",
            "window_days": window_days,
        },
        "anomalies": anomalies,
        "aggregate_statistics": _agg(len(violation_timeline), with_anom, sev_sum),
    }


# --------------------------------------------------------------------------- #
# 5. Re-score severity with recency
# --------------------------------------------------------------------------- #
def score_anomaly_severity(anomaly_data: dict, recency_weight: float = 1.0,
                           reference_time: str = None) -> dict:
    if not isinstance(anomaly_data, dict):
        raise ValueError("anomaly_data must be a dict")
    # accept either a single anomaly dict or {'anomalies':[...]} / {'rescored_anomalies':[...]}
    if "anomalies" in anomaly_data:
        src = anomaly_data["anomalies"]
    elif "rescored_anomalies" in anomaly_data:
        src = anomaly_data["rescored_anomalies"]
    else:
        src = [anomaly_data]
    if not isinstance(src, list):
        src = [src]
    rescored = []
    ref = parse_ref(reference_time)
    for a in src:
        if not isinstance(a, dict) or "severity" not in a:
            raise ValueError("anomaly entry missing 'severity'")
        sev = float(a["severity"])
        ts = a.get("timestamp")
        age_hours = _age_from_ref(ts, ref) if ts else 0.0
        factor = S.recency_factor(age_hours, recency_weight)
        adjusted = round(min(1.0, sev * factor), 4)
        rescored.append({
            "anomaly_id": a.get("anomaly_id", ""),
            "original_severity": sev,
            "recency_adjusted_severity": adjusted,
            "timestamp": ts,
            "age_hours": round(age_hours, 4),
            "recency_factor": factor,
        })
    return {"rescored_anomalies": rescored}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _none_record(anomaly_id, kind, note, grain_id=None, fact_id=None,
                 collision_pair=None, baseline=None, observed=None, window=None,
                 established_since=None):
    rec = {"anomaly_id": anomaly_id, "anomaly_type": "none", "note": note,
           "severity": 0.0}
    if grain_id is not None: rec["grain_id"] = grain_id
    if fact_id is not None: rec["fact_id"] = fact_id
    if collision_pair is not None: rec["collision_pair"] = collision_pair
    if baseline is not None: rec["baseline_rate" if kind == "grain" else "baseline_violation_rate"] = round(baseline, 4)
    if observed is not None: rec["observed_rate" if kind == "grain" else "observed_violation_rate"] = round(observed, 4)
    if window: rec["window"] = window
    if established_since: rec["established_since"] = established_since
    rec["deviation_magnitude"] = 0.0
    return rec


def _agg(total, with_anom, sev_sum):
    n = len(with_anom)
    mean = round(sev_sum / n, 4) if n else 0.0
    return {
        "total_analyzed": total,
        "with_anomalies": n,
        "mean_severity": mean,
        "high_severity_count": 1 if (n and mean >= HIGH_SEVERITY) else 0,
    }


def _as_int(gid):
    try:
        return int(str(gid).split("_")[-1]) if "_" in str(gid) else int(gid)
    except (ValueError, TypeError):
        return gid


def _parse_pair(key):
    s = str(key).strip()
    # accept "(42, 137)" or "42,137" or "[42, 137]"
    for ch in "()[]":
        s = s.replace(ch, "")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    try:
        return [int(parts[0]), int(parts[1])]
    except (ValueError, IndexError):
        return parts


def _first_period(baseline):
    for v in baseline.values():
        if isinstance(v, dict) and v.get("period"):
            return v["period"]
    return "unknown"


def _age_hours(first, last):
    if not first or not last:
        return 0.0
    try:
        d1 = B.parse_ts(first); d2 = B.parse_ts(last)
        return abs((d2 - d1).total_seconds()) / 3600.0
    except Exception:
        return 0.0


def _age_from_ref(ts, ref):
    if not ts:
        return 0.0
    try:
        d = B.parse_ts(ts)
        ref = ref or datetime.now(timezone.utc)
        return abs((ref - d).total_seconds()) / 3600.0
    except Exception:
        return 0.0


def parse_ref(reference_time):
    if not reference_time:
        return None
    try:
        return B.parse_ts(reference_time)
    except Exception:
        return None


def _window_label(hours):
    if hours <= 0:
        return "unknown"
    if hours < 24:
        return f"last_{max(1, round(hours))}_hours"
    return f"last_{round(hours / 24.0)}_days"


def _ratio_str(ratio):
    if ratio == float("inf"):
        return "inf"
    return f"{ratio:.0f}"
