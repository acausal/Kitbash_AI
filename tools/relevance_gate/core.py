"""tools.relevance_gate core: deterministic query-time relevance filter.

Wraps already-built tools/ packages (no new NLP). See docs/SPEC-relevance_gate_v1.md.
Public API matches the spec exactly:
  score_candidates(query, context, candidates, weights=None) -> List[dict]
  is_ambiguous(scored, margin_threshold=0.15, volume_threshold=8) -> bool
  apply_relevance_gate(query, context, candidates, weights=None, top_k=None) -> dict

Isolation contract: imports stdlib, other tools/, and core historical_common
(read-only helper). No orchestrator/engine/redis imports.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Sequence

from tools.historical_common import normalize_config, normalize_token_list
from tools.duplicate_detection import detect_duplicates
from tools.tfidf_ranker.core import compute_tfidf, bm25_score
from tools.cosine_similarity.core import compute_similarity
from tools.ner.core import extract_entities
from tools.svo.core import extract_svo
from tools.negation_detector.core import detect_negations

from .gate_schema import SIMILARITY_BUCKET_NUMERIC


DEFAULT_WEIGHTS = {
    "lexical": 0.35,
    "similarity_bucket": 0.25,
    "entity_overlap": 0.20,
    "structural_overlap": 0.20,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tokens(text: str, cfg) -> List[str]:
    return normalize_token_list(text.split(), cfg)


def _entity_texts(text: str) -> set:
    """Entity-text set for Jaccard. Raises if spaCy is unavailable
    (fail-loud per spec — no silent lexical-only degrade)."""
    return {e.text.lower() for e in extract_entities(text)}


def _svo_fields(text: str) -> List[str]:
    """Flatten SVO triples to a bag of field tokens for partial-match Jaccard.
    Raises if spaCy is unavailable (fail-loud per spec)."""
    fields = []
    for svo in extract_svo(text):
        for val in (svo.subject, svo.verb, svo.obj):
            if val:
                fields.append(str(val).lower())
    return fields


def _has_negation(text: str) -> bool:
    """True if the text carries a detected negation. Raises if spaCy is
    unavailable (fail-loud per spec)."""
    return any(getattr(t, "is_negated", False) for t in detect_negations(text))


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return (inter / union) if union else 0.0


def _normalize_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Port (not import) of the positive_signal_scorer normalization pattern."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for k in w:
            if k in weights:
                if not isinstance(weights[k], (int, float)) or weights[k] < 0:
                    raise ValueError(f"invalid weight for {k}: {weights[k]!r}")
                w[k] = float(weights[k])
        total = sum(w.values())
        if total <= 0:
            raise ValueError("weights sum to zero")
        w = {k: v / total for k, v in w.items()}
    return w


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def score_candidates(
    query: str,
    context: str,
    candidates: List[dict],
    weights: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """Score each candidate on lexical / similarity / entity / structural dims.

    Returns a list of dicts (JSON-serializable) matching the spec's
    ScoredCandidate shape: {id, relevance_strength, dims{...}, negation_flag}.
    """
    if not candidates:
        return []

    cfg = normalize_config(None)
    q_tokens = _tokens(query, cfg)
    q_entities = _entity_texts(query)
    q_svo = _svo_fields(query)
    q_neg = _has_negation(query)

    # Build TF-IDF corpus over the candidate set for IDF + BM25.
    corpus = [{"id": c["id"], "tokens": _tokens(c.get("text", ""), cfg)} for c in candidates]
    tfidf = compute_tfidf(corpus, {"tfidf_variant": "bm25"})
    idf = tfidf["idf"]
    avgdl = tfidf["metadata"].get("avg_doc_length", 0.0) or 0.0

    w = _normalize_weights(weights)
    out = []
    for c in candidates:
        cid = c["id"]
        ctext = c.get("text", "")
        c_tokens = _tokens(ctext, cfg)

        # lexical: BM25 over the candidate set's idf table
        lexical = bm25_score(q_tokens, c_tokens, idf, avgdl) if q_tokens and c_tokens else 0.0

        # similarity_bucket: cosine over TF-IDF vectors -> interpret -> numeric
        q_vec = tfidf["document_vectors"].get("_q")
        c_vec = tfidf["document_vectors"].get(cid, {})
        similarity_bucket = 0.0
        if q_vec and c_vec:
            sim_res = compute_similarity(q_vec, c_vec)
            label = sim_res["result"]["interpretation"]
            similarity_bucket = SIMILARITY_BUCKET_NUMERIC.get(label, 0.0)

        # entity_overlap: Jaccard of entity-text sets (query vs candidate)
        c_entities = _entity_texts(ctext)
        entity_overlap = _jaccard(q_entities, c_entities)

        # structural_overlap: partial-match Jaccard over SVO field bags
        c_svo = _svo_fields(ctext)
        structural_overlap = _jaccard(set(q_svo), set(c_svo))

        # negation_flag: polarity mismatch (metadata only, not scored)
        c_neg = _has_negation(ctext)
        negation_flag = (q_neg != c_neg)

        dims = {
            "lexical": round(lexical, 6),
            "similarity_bucket": round(similarity_bucket, 6),
            "entity_overlap": round(entity_overlap, 6),
            "structural_overlap": round(structural_overlap, 6),
        }
        relevance = (
            w["lexical"] * lexical
            + w["similarity_bucket"] * similarity_bucket
            + w["entity_overlap"] * entity_overlap
            + w["structural_overlap"] * structural_overlap
        )
        out.append({
            "id": cid,
            "relevance_strength": round(relevance, 6),
            "dims": dims,
            "negation_flag": negation_flag,
        })
    return out


# ---------------------------------------------------------------------------
# ambiguity trigger
# ---------------------------------------------------------------------------
def is_ambiguous(
    scored: List[dict],
    margin_threshold: float = 0.15,
    volume_threshold: int = 8,
) -> bool:
    """Either trigger trips it: close top-2 margin, or candidate volume overflow."""
    if len(scored) > volume_threshold:
        return True
    if len(scored) < 2:
        return False
    ordered = sorted(scored, key=lambda s: s["relevance_strength"], reverse=True)
    margin = ordered[0]["relevance_strength"] - ordered[1]["relevance_strength"]
    return margin < margin_threshold


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def apply_relevance_gate(
    query: str,
    context: str,
    candidates: List[dict],
    weights: Optional[Dict[str, float]] = None,
    top_k: Optional[int] = None,
) -> dict:
    """Dedup -> score -> is_ambiguous -> select.

    Not ambiguous: documented no-op pass-through (gate_fired=False).
    Ambiguous: filter to top_k (or min-strength cutoff), gate_fired=True,
    trigger recorded.
    """
    # Error semantics (per spec): malformed candidate -> ValueError, loud.
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list of dicts")
    for c in candidates:
        if not isinstance(c, dict) or "id" not in c or not isinstance(c.get("text"), str):
            raise ValueError(f"malformed candidate (need id + text str): {c!r}")

    if not candidates:
        return {
            "gate_fired": False,
            "trigger": None,
            "selected": [],
            "all_scored": [],
            "negation_flags": [],
            "note": "empty candidate set",
        }

    # 1. Dedup via duplicate_detection (jaccard). Keep representative, drop members.
    cfg = normalize_config(None)
    dup_corpus = [{"id": c["id"], "tokens": _tokens(c.get("text", ""), cfg)} for c in candidates]
    try:
        dup = detect_duplicates(dup_corpus, strategy="jaccard", threshold=0.9)
        dropped = set()
        for g in dup.get("duplicate_groups", []):
            dropped.update(g["members"])
            dropped.discard(g["representative"])
        deduped = [c for c in candidates if c["id"] not in dropped]
    except Exception:
        # Dedup failure must not block the gate; fall back to all candidates.
        deduped = candidates

    # 2. Score
    scored = score_candidates(query, context, deduped, weights)

    # 3. Ambiguity
    ambiguous = is_ambiguous(scored)
    if not ambiguous:
        return {
            "gate_fired": False,
            "trigger": None,
            "selected": [s["id"] for s in scored],
            "all_scored": scored,
            "negation_flags": [s["id"] for s in scored if s["negation_flag"]],
            "note": "retrieval not ambiguous; pass-through",
        }

    # 4. Select
    ordered = sorted(scored, key=lambda s: s["relevance_strength"], reverse=True)
    trigger = "volume" if len(scored) > 8 else "margin"
    if top_k is not None:
        selected = [s["id"] for s in ordered[:top_k]]
    else:
        # min-strength cutoff: keep everything that isn't clearly irrelevant
        selected = [s["id"] for s in ordered if s["relevance_strength"] >= 0.1]
        if not selected:
            selected = [ordered[0]["id"]]  # always keep the best

    return {
        "gate_fired": True,
        "trigger": trigger,
        "selected": selected,
        "all_scored": scored,
        "negation_flags": [s["id"] for s in scored if s["negation_flag"]],
        "note": f"ambiguous ({trigger}); {len(selected)} of {len(scored)} selected",
    }
