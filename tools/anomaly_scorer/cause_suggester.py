"""Heuristic cause suggestion for tools.anomaly_scorer (stdlib only)."""

# Maps (anomaly_type, magnitude_band) -> possible causes. Bands: 'high' (>=3x),
# 'low' (<3x), 'emerging' (new/unknown), 'accel' (established pair accelerating).
_CAUSES = {
    "sudden_increase_false_positives": {
        "high": ["search_weight_shift", "query_pattern_change",
                 "grain_confusion_emergence"],
        "low": ["transient_noise", "sampling_variance"],
    },
    "sudden_decrease_false_positives": {
        "high": ["search_weight_overcorrection", "query_pattern_concentration"],
        "low": ["sampling_variance"],
    },
    "confidence_degradation": {
        "high": ["query_ambiguity_increase", "knowledge_base_drift",
                 "context_confusion"],
        "low": ["transient_noise"],
    },
    "collision_emergence": {
        "emerging": ["grain_structural_similarity_emergence",
                     "query_pattern_concentration"],
    },
    "collision_acceleration": {
        "accel": ["search_reweighting", "ternary_delta_change"],
    },
    "trend_shift": {
        "high": ["systematic_knowledge_base_change", "query_distribution_shift",
                 "coherence_degradation"],
    },
    "violation_acceleration": {
        "high": ["systematic_knowledge_base_change", "coherence_degradation",
                 "epistemological_layer_shift"],
    },
}


def suggest_causes(anomaly_type: str, magnitude_ratio: float = 0.0,
                   is_emerging: bool = False, is_accel: bool = False) -> list:
    """Return a list of suggested cause strings for an anomaly type."""
    table = _CAUSES.get(anomaly_type, {})
    if is_emerging and "emerging" in table:
        return list(table["emerging"])
    if is_accel and "accel" in table:
        return list(table["accel"])
    band = "high" if magnitude_ratio >= 3.0 else "low"
    return list(table.get(band, ["data_drift"]))


def recommend(anomaly_type: str, target: str, detail: str = "") -> str:
    """Human-readable recommendation string."""
    base = {
        "sudden_increase_false_positives":
            f"Investigate {target}'s recent ternary deltas; check query patterns for shift",
        "sudden_decrease_false_positives":
            f"Review whether {target}'s fp-rate drop is genuine improvement or suppression",
        "confidence_degradation":
            f"Re-examine {target} with MTR layer; check for ternary delta drift",
        "collision_emergence":
            f"Monitor {target} for rapid growth; may indicate emerging structural similarity",
        "collision_acceleration":
            f"Rebalance grain weights for {target}; inspect recent ternary deltas",
        "trend_shift":
            f"Investigate what changed recently for {target}; check MTR state and query shifts",
        "violation_acceleration":
            f"Audit {target} coherence path; check epistemological layer drift",
    }
    return base.get(anomaly_type, f"Investigate {target} anomaly") + (f"; {detail}" if detail else "")
