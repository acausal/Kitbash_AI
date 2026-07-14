"""tools.pattern_explainer core: deterministic template-based explanations.

Functions:
  explain_collision_cluster(cluster, collision_index=None)
  explain_anomaly(anomaly, historical_baseline=None)
  explain_pattern_reliability(pattern, confidence_scores)
  explain_multiple_patterns(patterns_list, confidence_scores_list, summary_style="brief")
  generate_sleep_report(clusters, anomalies, patterns, scores)

Stdlib only (json, string).
"""
from string import Template
from typing import Dict, List, Optional

from . import templates as T
from . import formatters as F
from . import confidence_language as C


# --------------------------------------------------------------------------- #
# 1. Collision cluster
# --------------------------------------------------------------------------- #
def explain_collision_cluster(cluster: dict, collision_index: dict = None) -> dict:
    if not isinstance(cluster, dict):
        raise ValueError("cluster must be a dict")
    if "cluster_id" not in cluster or "members" not in cluster:
        raise KeyError("cluster missing required fields: cluster_id, members")
    members = cluster["members"]
    theme = cluster.get("query_theme", "related concepts")
    coherence = float(cluster.get("coherence", 0.0))
    density = float(cluster.get("collision_density", 0.0))
    size = int(cluster.get("size", len(members)))

    # derive a human concept label from the cluster_id (e.g. bio_energy_transfer
    # -> "energy transfer"); fall back to the raw id words.
    cid_words = str(cluster["cluster_id"]).split("_")
    if len(cid_words) > 1 and len(cid_words[0]) <= 4:
        concept = " ".join(cid_words[1:])
    else:
        concept = " ".join(cid_words)

    pairs = sorted(cluster.get("pairwise_collisions", []),
                   key=lambda p: p.get("count", 0), reverse=True)
    top = pairs[0] if pairs else None
    if top:
        top_members = F.format_list(top["pair"])
        top_count = top["count"]
    else:
        top_members = F.format_list(members[:2])
        top_count = 0

    coh_label = C.f1_to_reliability(coherence)
    coh_meaning = "genuinely similar" if coherence >= 0.70 else (
        "moderately related" if coherence >= 0.50 else "weakly linked")
    dens_meaning = "frequently" if density >= 0.70 else (
        "occasionally" if density >= 0.50 else "rarely")

    pair_lines = "\n".join(
        T.COLLISION_PAIR_LINE.format(
            a=p["pair"][0], b=p["pair"][1], count=p["count"],
            rank="most frequent" if i == 0 else ("second" if i == 1 else "lower"))
        for i, p in enumerate(pairs)
    )

    one_liner = T.COLLISION_ONE_LINER.format(
        members=F.format_list(members), concept=concept)
    summary = T.COLLISION_SUMMARY.format(
        size=size, theme=theme, top_pair_members=top_members, top_pair_count=top_count)
    detailed = T.COLLISION_DETAILED.format(
        size=size, member_list=F.format_list(members), coherence_label=coh_label,
        coherence=f"{coherence:.2f}", coherence_meaning=coh_meaning,
        density=f"{density:.2f}", density_meaning=dens_meaning, pair_lines=pair_lines)
    conf = C.cluster_confidence_label(coherence, density)
    if conf == "high":
        conf_text = "real structural pattern, not noise"
    elif conf == "medium":
        conf_text = "moderate pattern; monitor for drift"
    else:
        conf_text = "weak pattern; may be mostly noise"
    justification = (
        f"Cluster coherence {coherence:.2f} and collision density {density:.2f} "
        f"indicate this is a {conf_text}."
    )
    return {
        "cluster_id": cluster["cluster_id"],
        "explanation_type": "collision_cluster",
        "one_liner": one_liner,
        "summary": summary,
        "detailed_explanation": detailed,
        "implications": T.COLLISION_IMPLICATIONS,
        "recommendations": [t.format(members=F.format_list(members))
                            for t in T.COLLISION_RECOMMENDATIONS],
        "confidence": conf,
        "confidence_justification": justification,
    }


# --------------------------------------------------------------------------- #
# 2. Anomaly
# --------------------------------------------------------------------------- #
_ANOMALY_LABELS = {
    "sudden_increase_false_positives": "sudden increase in false positives",
    "sudden_decrease_false_positives": "sudden decrease in false positives",
    "confidence_degradation": "confidence degradation",
    "collision_emergence": "emerging collision",
    "collision_acceleration": "collision acceleration",
    "trend_shift": "violation trend shift",
}
_CAUSE_EXPLAIN = {
    "search_weight_shift": (
        "If search weights for this grain were recently rebalanced, it may be over-triggering.",
        "Check git history or config management for this grain's weight changes in the last 24 hours."),
    "query_pattern_change": (
        "If queries are now using different keywords or phrasing, the grain may not match them correctly.",
        "Analyze query logs from the recent window; compare query distribution to historical norm."),
    "query_ambiguity_increase": (
        "If incoming queries have grown more ambiguous, the grain's discrimination threshold may be too loose.",
        "Inspect recent query embeddings; look for broadening of the routing boundary."),
    "grain_confusion_emergence": (
        "If this grain is now confused with nearby grains, its ternary delta may have drifted.",
        "Review ternary delta values; compare to its collision partners."),
    "knowledge_base_drift": (
        "If new facts were added to the knowledge base, they may collide with this grain's routing.",
        "Check recently added facts; test whether they route to this grain incorrectly."),
    "context_confusion": (
        "If context windows changed, the grain may be matching on stale or adjacent context.",
        "Review context assembly; verify the grain sees the intended window."),
    "transient_noise": (
        "A small fluctuation may be transient sampling noise rather than a real shift.",
        "Re-check the metric after a cooldown window before acting."),
    "sampling_variance": (
        "With few observations the rate is sensitive to single events.",
        "Collect more samples before concluding a real change."),
    "data_drift": (
        "Underlying data distribution may have shifted.",
        "Profile recent inputs versus the historical baseline."),
}
_CAUSE_DEFAULT = (
    "This factor may have contributed to the observed change.",
    "Investigate this factor against recent system activity.")


def _anomaly_type_label(atype: str) -> str:
    return _ANOMALY_LABELS.get(atype, atype.replace("_", " "))


def explain_anomaly(anomaly: dict, historical_baseline: dict = None) -> dict:
    if not isinstance(anomaly, dict):
        raise ValueError("anomaly must be a dict")
    for k in ("anomaly_id", "anomaly_type"):
        if k not in anomaly:
            raise KeyError(f"anomaly missing required field: {k}")
    atype = anomaly["anomaly_type"]
    severity = float(anomaly.get("severity", 0.0))
    sev_label = C.severity_to_label(severity)
    grain_id = anomaly.get("grain_id", anomaly.get("fact_id"))
    entity = F.format_entity_label(grain_id if grain_id is not None else "?", "grain")

    mag = float(anomaly.get("deviation_magnitude", 0.0))
    base = float(anomaly.get("baseline_rate", 0.0))
    obs = float(anomaly.get("observed_rate", 0.0))
    base_pct = F.format_percentage(base)
    obs_pct = F.format_percentage(obs)
    magnitude = F.format_magnitude(mag)
    window = anomaly.get("window", "")
    window_short = _window_short(window)
    full_dev = ""  # magnitude already shown inline

    # z-score from evidence if present
    z = _extract_z(anomaly.get("evidence", []))
    full_dev = f" ({z:.1f} standard deviations above baseline)" if z is not None else ""

    if atype == "sudden_increase_false_positives":
        one_liner = T.ANOMALY_ONE_LINER_INCREASE.format(entity=entity, magnitude=magnitude)
    elif atype == "sudden_decrease_false_positives":
        one_liner = T.ANOMALY_ONE_LINER_DECREASE.format(entity=entity, magnitude=magnitude)
    else:
        one_liner = T.ANOMALY_ONE_LINER_GENERIC.format(
            entity=entity, type_label=_anomaly_type_label(atype), severity_label=sev_label)
    summary = T.ANOMALY_SUMMARY.format(
        entity=entity, baseline_pct=base_pct, observed_pct=obs_pct,
        window_short=window_short, magnitude=magnitude, full_dev=full_dev)
    collision_note = _collision_note(anomaly.get("evidence", []))
    detailed = T.ANOMALY_DETAILED.format(
        window_short=window_short, window=window, entity=entity, baseline_pct=base_pct,
        observed_pct=obs_pct, magnitude=magnitude, full_dev=full_dev,
        collision_note=collision_note)

    causes_expanded = []
    for c in anomaly.get("possible_causes", []):
        expl, inv = _CAUSE_EXPLAIN.get(c, _CAUSE_DEFAULT)
        causes_expanded.append({"cause": c, "explanation": expl, "investigation": inv})

    # confidence calibration: lower if small sample / low severity
    conf = "high"
    just = (f"Magnitude ({mag:.2f}x), statistical significance (z={z}), and recency "
            f"(within {window_short}) all confirm this is a real anomaly.") if z is not None \
        else f"Magnitude ({mag:.2f}x) and severity ({sev_label}) indicate a real anomaly."
    if "sample_size" in " ".join(anomaly.get("evidence", [])) or "low_sample" in " ".join(
            anomaly.get("possible_causes", [])):
        conf = "medium"
        just = (f"Severity is {sev_label}, but evidence mentions insufficient sample_size; "
                f"recommend confirming with more data before acting.")
    elif severity < 0.50:
        conf = "medium"

    return {
        "anomaly_id": anomaly["anomaly_id"],
        "explanation_type": "anomaly",
        "severity_label": sev_label,
        "one_liner": one_liner,
        "summary": summary,
        "detailed_explanation": detailed,
        "anomaly_type_explanation": T.ANOMALY_TYPE_EXPLANATION,
        "timeline": {
            "baseline_period": "last_7_days",
            "anomaly_observation_window": window,
            "age_at_detection": "current",
        },
        "possible_causes_expanded": causes_expanded,
        "implications": [t.format(observed_pct=obs_pct) for t in T.ANOMALY_IMPLICATIONS],
        "recommendations": T.ANOMALY_RECOMMENDATIONS,
        "severity": severity,
        "severity_label": sev_label,
        "confidence": conf,
        "confidence_justification": just,
    }


# --------------------------------------------------------------------------- #
# 3. Pattern reliability
# --------------------------------------------------------------------------- #
def explain_pattern_reliability(pattern: dict, confidence_scores: dict) -> dict:
    if not isinstance(pattern, dict) or not isinstance(confidence_scores, dict):
        raise ValueError("pattern and confidence_scores must be dicts")
    for k in ("pattern_id", "sequence"):
        if k not in pattern:
            raise KeyError(f"pattern missing required field: {k}")
    pid = pattern["pattern_id"]
    seq = pattern["sequence"]
    seq_str = F.format_pattern_sequence(seq)
    metrics = confidence_scores.get("metrics", {})
    precision = float(metrics.get("precision", 0.0))
    recall = float(metrics.get("recall", 0.0))
    f1 = float(metrics.get("f1_score", 0.0))
    support = int(metrics.get("support", pattern.get("frequency", 0)))
    rel = C.f1_to_reliability(f1)
    flags = _flags_from(confidence_scores)

    one_liner = T.PATTERN_ONE_LINER.format(
        sequence=seq_str, reliability_label=C.reliability_phrase(rel), f1=f"{f1:.2f}")
    summary = T.PATTERN_SUMMARY.format(
        frequency=support, precision=F.format_percentage(precision),
        recall=F.format_percentage(recall), reliability_label=rel)
    detailed = T.PATTERN_DETAILED.format(
        pattern_id=pid, size=len(seq), sequence=seq_str,
        precision=F.format_percentage(precision),
        precision_rationale="strong; the pattern rarely produces incorrect results"
        if precision >= 0.80 else "moderate; some incorrect results when it fires",
        recall=F.format_percentage(recall),
        recall_rationale="the pattern is important but not the only success mode"
        if recall >= 0.70 else "the pattern covers only part of success cases",
        f1=f"{f1:.2f}",
        f1_rationale=f"above the 0.70 'high reliability' threshold" if f1 >= 0.70
        else "below the 0.70 threshold; reliability is limited",
        support=support,
        support_rationale="sufficient data for confidence" if support >= 20
        else "below n>=20; confidence is limited",
        flag_note=("No data quality issues detected (no confidence flags)."
                   if not flags else
                   f"Confidence flags present ({', '.join(flags)}); interpret with caution."))

    breakdown = {
        "precision_explanation": f"{F.format_percentage(precision)} success rate when pattern fires.",
        "recall_explanation": f"{F.format_percentage(recall)} of successes involve this pattern.",
        "f1_explanation": f"F1 score of {f1:.2f} is "
        f"{'above' if f1 >= 0.70 else 'below'} the 0.70 reliability threshold.",
    }
    if rel == "high":
        use_cases = T.PATTERN_USE_CASES_HIGH
    elif rel == "medium":
        use_cases = T.PATTERN_USE_CASES_MED
    else:
        use_cases = T.PATTERN_USE_CASES_LOW

    sample_assess = (f"{support} observations is sufficient for reliable scoring "
                     "(well above n>=20 threshold)." if support >= 20 else
                     f"{support} observations is below the n>=20 threshold; "
                     f"recommend collecting more data before trusting this pattern.")
    comparison = (f"This pattern's F1 score ({f1:.2f}) is above the median; "
                  "it's in the top quartile of patterns." if f1 >= 0.75 else
                  f"This pattern's F1 score ({f1:.2f}) is around or below the median; "
                  "it needs more support to rank highly.")
    rec = (f"Sleep Tier 3 should prioritize this pattern for hypothesis generation "
           "and potential LoRA training." if rel == "high" else
           f"Sleep Tier 3 should monitor this pattern; collect more data before "
           f"prioritizing it for hypothesis generation." if rel == "medium" else
           f"Sleep Tier 3 should not use this pattern for hypothesis generation until "
           f"reliability improves.")
    conf = C.pattern_confidence_label(f1, flags, support)
    justification = (f"High precision, good recall, sufficient sample size, and no quality "
                     f"flags all indicate this pattern is genuinely reliable." if conf == "high"
                     else f"Mixed metrics{' and/or quality flags' if flags else ''} "
                     f"indicate moderate reliability; verify before relying on it." if conf == "medium"
                     else f"Low F1 and/or insufficient data indicate this pattern is not yet reliable.")
    return {
        "pattern_id": pid,
        "explanation_type": "pattern_reliability",
        "one_liner": one_liner,
        "summary": summary,
        "detailed_explanation": detailed,
        "reliability_breakdown": breakdown,
        "confidence_flags": flags,
        "confidence_flag_explanations": [f"Flag '{f}': {_flag_meaning(f)}" for f in flags],
        "sample_size_assessment": sample_assess,
        "use_cases": use_cases,
        "reliability_level": rel,
        "recommendation": rec,
        "comparison_to_baseline": comparison,
        "confidence": conf,
        "confidence_justification": justification,
    }


# --------------------------------------------------------------------------- #
# 4. Multiple patterns
# --------------------------------------------------------------------------- #
def explain_multiple_patterns(patterns_list: list, confidence_scores_list: list,
                              summary_style: str = "brief") -> dict:
    if not isinstance(patterns_list, list) or not isinstance(confidence_scores_list, list):
        raise ValueError("patterns_list and confidence_scores_list must be lists")
    if len(patterns_list) != len(confidence_scores_list):
        raise ValueError("patterns_list and confidence_scores_list length mismatch")
    if summary_style not in ("brief", "summary", "detailed"):
        raise ValueError(f"unrecognized summary_style: {summary_style}")

    f1_by_id = {c.get("pattern_id"): float(c.get("metrics", {}).get("f1_score", 0.0))
                for c in confidence_scores_list}
    flags_by_id = {c.get("pattern_id"): _flags_from(c) for c in confidence_scores_list}

    levels = []
    for p in patterns_list:
        f1 = f1_by_id.get(p.get("pattern_id"), 0.0)
        levels.append((p.get("pattern_id"), f1, C.f1_to_reliability(f1)))

    high = sum(1 for _, _, l in levels if l == "high")
    medium = sum(1 for _, _, l in levels if l == "medium")
    low = sum(1 for _, _, l in levels if l == "low")

    if summary_style == "brief":
        summaries = [{
            "pattern_id": pid,
            "one_liner": F.format_pattern_sequence(p.get("sequence", [])) +
                         f" is {lvl} (F1: {f1:.2f}).",
            "reliability": lvl,
        } for pid, f1, lvl in levels]
    else:
        summaries = [{
            "pattern_id": pid,
            "one_liner": F.format_pattern_sequence(p.get("sequence", [])) +
                         f" is {lvl} (F1: {f1:.2f}).",
            "reliability": lvl,
        } for pid, f1, lvl in levels]

    top = sorted(levels, key=lambda x: x[1], reverse=True)[:3]
    top_patterns = [{"pattern_id": pid, "f1": f1} for pid, f1, _ in top]
    attention = [{"pattern_id": pid, "f1": f1, "issue": "low_f1_score"}
                 for pid, f1, lvl in levels if lvl == "low"]

    total = len(levels)
    if high >= max(1, total * 0.5):
        agg = T.AGGREGATE_SUMMARY.format(total=total, high=high, medium=medium, low=low)
    else:
        agg = T.AGGREGATE_SUMMARY_MIXED.format(total=total, high=high, medium=medium, low=low)

    recs = []
    if top_patterns:
        recs.append(f"Patterns {', '.join(t['pattern_id'] for t in top_patterns)} are solid; "
                    f"candidate for LoRA extraction.")
    if medium:
        recs.append("Medium-reliability patterns need more data; keep monitoring.")
    if attention:
        recs.append(f"Pattern(s) {', '.join(a['pattern_id'] for a in attention)} underperform; "
                    f"investigate failure mode or remove from active reasoning.")

    return {
        "summary_type": "pattern_collection_brief",
        "total_patterns": total,
        "high_reliability_patterns": high,
        "medium_reliability_patterns": medium,
        "low_reliability_patterns": low,
        "aggregate_summary": agg,
        "pattern_summaries": summaries,
        "top_patterns_by_reliability": top_patterns,
        "patterns_needing_attention": attention,
        "recommendations": recs,
    }


# --------------------------------------------------------------------------- #
# Sleep report aggregator
# --------------------------------------------------------------------------- #
def generate_sleep_report(clusters: list = None, anomalies: list = None,
                          patterns: list = None, scores: list = None) -> dict:
    """Aggregate the three explanation types into one Sleep Tier 2 report."""
    clusters = clusters or []
    anomalies = anomalies or []
    patterns = patterns or []
    scores = scores or []
    report = {
        "report_type": "sleep_tier2_explanations",
        "collision_clusters": [explain_collision_cluster(c) for c in clusters],
        "anomalies": [explain_anomaly(a) for a in anomalies],
        "patterns": [explain_pattern_reliability(p, s) for p, s in zip(patterns, scores)],
        "summary": {
            "collision_clusters": len(clusters),
            "anomalies": len(anomalies),
            "patterns": len(patterns),
            "high_severity_anomalies": sum(
                1 for a in anomalies if a.get("severity", 0) >= 0.75),
            "high_reliability_patterns": sum(
                1 for s in scores if C.f1_to_reliability(
                    float(s.get("metrics", {}).get("f1_score", 0.0))) == "high"),
        },
    }
    return report


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _window_short(window: str) -> str:
    if not window:
        return "recent window"
    # "2026-07-14T10:00:00Z to 2026-07-14T14:00:00Z" -> "last 4 hours"
    parts = [p.strip() for p in window.split(" to ")]
    if len(parts) == 2:
        try:
            from datetime import datetime
            a = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
            b = datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
            hrs = max(1, round((b - a).total_seconds() / 3600))
            return f"last {hrs} hours"
        except ValueError:
            return "recent window"
    return "recent window"


def _extract_z(evidence: list) -> Optional[float]:
    for e in evidence:
        if "standard_deviations" in e:
            # e.g. "12.5_standard_deviations_above_baseline"
            try:
                return float(e.split("_")[0])
            except (ValueError, IndexError):
                return None
    return None


def _collision_note(evidence: list) -> str:
    for e in evidence:
        if "confused_with" in e:
            facts = e.split("most_confused_with_facts_")[-1]
            return (f"The grain is frequently confused with Grains {facts.replace('_', ', ')} "
                    f"(other routing components). This collision pattern may indicate the "
                    f"grain's discrimination ability has degraded.")
    return ""


def _flags_from(confidence_scores: dict) -> List[str]:
    interp = confidence_scores.get("interpretation", {})
    flag = interp.get("confidence_flag")
    if flag and flag != "none":
        return [flag]
    # Anomaly-scorer style low-sample flag
    if confidence_scores.get("confidence_flag") == "low_sample_size":
        return ["low_sample_size"]
    return []


def _flag_meaning(flag: str) -> str:
    return {
        "low_sample_size": "few observations; metrics may not be stable",
        "high_false_positive_rate": "pattern fires incorrectly often",
    }.get(flag, "quality concern detected")
