"""Core orchestration for tools.multispectral_analyzer (see SPEC).

analyze_multispectral(): validate -> run spectra -> fingerprint -> divergences.
Two divergence rules (spec §5.2, restated in MVP §1.3):
  - confidence_mismatch:       high tfidf_mean AND high negation_ratio
  - semantic_density_mismatch: high entity_density AND low tfidf_mean
Plus one optional (post-MVP candidate, kept simple): entropy_anomaly
  - entropy_anomaly:           high entropy but low negation_ratio
All threshold-based, flag-only (no action). Thresholds are MVP guesses.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, List, Optional

from .schema import DivergenceFlag, MultispectralResult, SpectrumResult
from . import spectrum_tools as st

TOOL_ID = "multispectral_analyzer"
VERSION = "v1"

# MVP divergence thresholds (spec §4.3 — explicit guesses, refine post-collection).
TFIDF_HIGH = 0.7
NEGATION_HIGH = 0.15
ENTITY_DENSITY_HIGH = 0.3
TFIDF_LOW = 0.4
ENTROPY_HIGH = 3.0


def analyze_multispectral(
    data: str,
    data_type: str = "text",
    spectrum_config: Optional[dict] = None,
    detect_divergence: bool = True,
) -> dict:
    """Main entry. Returns the full multispectral result dict (envelope-ready)."""
    if not isinstance(data, str) or data.strip() == "":
        raise ValueError("data must be a non-empty string")
    if data_type not in ("text", "json", "log"):
        raise ValueError(f"invalid data_type '{data_type}' (expected text/json/log)")
    if data_type != "text":
        # JSON/log spectra are deferred (spec §9.3). Be explicit, don't silently run text.
        raise ValueError(f"data_type '{data_type}' not supported in MVP (text only)")

    cfg = spectrum_config or {}
    enabled = cfg.get("enabled") or list(st.DEFAULT_SPECTRA)
    disabled = set(cfg.get("disabled") or [])
    enabled = [s for s in enabled if s not in disabled and s in st.SPECTRUM_TOOL_MAP]
    if not enabled:
        raise ValueError("spectrum_config enabled no known spectra")

    spectral = st.run_all_spectra(data, enabled)
    spectral_results = {k: SpectrumResult(**v) for k, v in spectral.items()}

    fingerprint_hash, signature = _fingerprint_and_signature(spectral_results)

    divergences: List[DivergenceFlag] = []
    if detect_divergence:
        divergences = detect_divergences(spectral_results)

    attempted = len(spectral_results)
    succeeded = sum(1 for r in spectral_results.values() if r.success)
    failed = attempted - succeeded

    from tools.historical_common import make_run_id, now_iso

    result = MultispectralResult(
        request_id=make_run_id("multispectral"),
        input_summary={
            "data_type": data_type,
            "data_length_chars": len(data),
            "data_hash": hashlib.sha256(data.encode("utf-8")).hexdigest()[:16],
        },
        spectral_results=spectral_results,
        fingerprint={"hash": fingerprint_hash, "signature": signature},
        divergence_flags=divergences,
        spectrum_config={
            "enabled": enabled,
            "disabled": sorted(disabled),
            "reason_disabled": "MVP: classification/markov need training; anomaly deferred",
        },
        execution_summary={
            "total_time_ms": sum(r.execution_time_ms for r in spectral_results.values()),
            "spectra_attempted": attempted,
            "spectra_succeeded": succeeded,
            "spectra_failed": failed,
            "failures": [
                {"spectrum": k, "error": r.error}
                for k, r in spectral_results.items()
                if not r.success
            ],
            "invoked_at": now_iso(),
        },
    )
    return _to_dict(result)


def _fingerprint_and_signature(spectral_results: Dict[str, SpectrumResult]):
    """SHA256 of sorted spectral outputs + a small numeric signature dict."""
    serializable = {
        k: ({"success": r.success, "output": r.output} if r.success else {"success": False, "error": r.error})
        for k, r in spectral_results.items()
    }
    blob = json.dumps(serializable, sort_keys=True, ensure_ascii=False, default=str)
    fingerprint_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    sig = {}
    # entity_density: entities per token
    ent = spectral_results.get("entities")
    surf = spectral_results.get("surface")
    tok_count = 0
    if surf and surf.success and isinstance(surf.output, list):
        tok_count = len(surf.output)
    if ent and ent.success and isinstance(ent.output, list):
        sig["entity_density"] = round(len(ent.output) / max(tok_count, 1), 4)
    # negation_ratio: negated tokens / tokens
    epi = spectral_results.get("epistemic")
    if epi and epi.success and isinstance(epi.output, list):
        negs = sum(1 for t in epi.output if getattr(t, "is_negated", False))
        sig["negation_ratio"] = round(negs / max(tok_count, 1), 4)
    # entropy: Shannon entropy of frequency_distribution
    freq = spectral_results.get("frequency")
    if freq and freq.success and isinstance(freq.output, dict):
        fdist = freq.output.get("frequency_distribution", {})
        sig["entropy"] = _shannon_entropy(fdist)
    # tfidf_mean: mean of ranking scores
    tw = spectral_results.get("semantic_weight")
    if tw and tw.success and isinstance(tw.output, dict):
        ranking = tw.output.get("ranking", [])
        scores = [_score_of(r) for r in ranking if isinstance(r, dict)]
        if scores:
            sig["tfidf_mean"] = round(sum(scores) / len(scores), 4)
    return fingerprint_hash, sig


def _score_of(r: dict) -> float:
    for key in ("tfidf", "score", "tf_idf"):
        if key in r and isinstance(r[key], (int, float)):
            return float(r[key])
    return 0.0


def _shannon_entropy(fdist: dict) -> float:
    if not fdist:
        return 0.0
    total = sum(v.get("frequency", 0) if isinstance(v, dict) else v for v in fdist.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for v in fdist.values():
        c = v.get("frequency", 0) if isinstance(v, dict) else v
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return round(h, 4)


def detect_divergences(spectral_results: Dict[str, SpectrumResult]) -> List[DivergenceFlag]:
    """Two MVP threshold rules + one optional. Flag-only, no action."""
    flags: List[DivergenceFlag] = []
    sig = _fingerprint_and_signature(spectral_results)[1]
    ent = sig.get("entity_density", 0.0)
    neg = sig.get("negation_ratio", 0.0)
    ent_h = sig.get("entropy", 0.0)
    tfidf = sig.get("tfidf_mean", 0.0)

    # 1) semantic_density_mismatch: many entities per token but low semantic weight
    if ent > ENTITY_DENSITY_HIGH and tfidf < TFIDF_LOW:
        flags.append(DivergenceFlag(
            "semantic_density_mismatch",
            ["entities", "semantic_weight"],
            f"entity_density={ent} (high) but tfidf_mean={tfidf} (low) -> boilerplate entities",
            "info",
        ))
    # 2) confidence_mismatch (restated): high semantic weight + high negation
    if tfidf > TFIDF_HIGH and neg > NEGATION_HIGH:
        flags.append(DivergenceFlag(
            "confidence_mismatch",
            ["semantic_weight", "epistemic"],
            f"tfidf_mean={tfidf} (high) but negation_ratio={neg} (high) -> conflicting signals",
            "warning",
        ))
    # optional: entropy_anomaly — diverse vocab but low negation (unusual distribution)
    if ent_h > ENTROPY_HIGH and neg < NEGATION_HIGH:
        flags.append(DivergenceFlag(
            "entropy_anomaly",
            ["frequency", "epistemic"],
            f"entropy={ent_h} (high) but negation_ratio={neg} (low) -> unusual distribution",
            "info",
        ))
    return flags


def _to_dict(result: MultispectralResult) -> dict:
    """Convert dataclasses to plain dict (envelope-ready)."""
    return {
        "request_id": result.request_id,
        "input_summary": result.input_summary,
        "spectral_results": {
            k: {
                "tool_id": r.tool_id,
                "success": r.success,
                "output": st._serialize(r.output) if r.output is not None else None,
                "error": r.error,
                "execution_time_ms": r.execution_time_ms,
            }
            for k, r in result.spectral_results.items()
        },
        "fingerprint": result.fingerprint,
        "divergence_flags": [
            {
                "divergence_type": d.divergence_type,
                "spectra_involved": d.spectra_involved,
                "description": d.description,
                "severity": d.severity,
            }
            for d in result.divergence_flags
        ],
        "spectrum_config": result.spectrum_config,
        "execution_summary": result.execution_summary,
    }
