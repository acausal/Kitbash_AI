# DEVNOTE: Relevance Gate v1 — Verification Audit

**Date:** 2026-07-15
**Subject:** `docs/SPEC-relevance_gate_v1.md` + companion `docs/PROPOSAL-BITNET_ROLE_RETIREMENT_AND_LOCAL_LLM_SWAP.md`
**Verdict:** SPEC IS ACCURATE AND BUILDABLE AS WRITTEN. No deviation note required — this is a verification audit, not a correction. (Contrast with `DEVNOTE-WEBUI_AND_TRACE_VISIBILITY.md` and the Error-Categorization redesign, where the specs were wrong.)

## What was verified against the real repo (2026-07-15)

### Proposal claims — all CONFIRMED
- Cascade order `GRAIN → BITNET → CARTRIDGE → ESCALATE`: `rule_based_triage.py::_insert_bitnet` (line 119) inserts BITNET immediately before CARTRIDGE → produces `[GRAIN, BITNET, CARTRIDGE, ESCALATE]`. Matches the proposal's stated drift exactly.
- BitNet threshold 0.65 < CARTRIDGE 0.70: confirmed (line 162: `BITNET: 0.65`, `CARTRIDGE: 0.70`).
- `ESCALATE` is a dead sentinel: `query_orchestrator_posix.py:291-292` — `if layer_name == ESCALATE_SENTINEL: break`. Nothing registered there. Matches proposal §1.
- "BitNet is the de facto only generation engine" — consistent with CARTRIDGE being the fallback and ESCALATE empty.

### Spec dependencies — all 6 tools PRESENT with the EXACT functions the spec calls
- `duplicate_detection.detect_duplicates(strategy="jaccard")` → dict with `duplicate_groups:[{members:[ids], representative:id}]` (core.py:71). Used for dedup collapse.
- `tfidf_ranker.core.bm25_score(query_tokens, doc_tokens, idf, avgdl, k, b)` (core.py:90). **NOTE:** requires a precomputed `idf` table + `avgdl`, NOT a corpus — the spec's pseudocode `bm25_score(query_tokens, doc_tokens, ...)` omitted these args. Build derives `idf`/`avgdl` via `compute_tfidf` over the candidate set (standard helper; SPEC notes the small-N IDF caveat, which is accepted).
- `cosine_similarity.core.compute_similarity(vec_a, vec_b) -> dict` with `result.cosine_similarity` + `result.interpretation`; `interpret()` returns labels `high_similarity`/`medium_similarity`/`low_similarity` (core.py:17,42). **NOTE:** the spec's mapping table shows `{low:0.0, medium:0.5, high:1.0}`, but the real labels are `low_similarity`/`medium_similarity`/`high_similarity` — the build maps the REAL labels (cosmetic spec/impl label mismatch, not a functional gap).
- `ner.core.extract_entities(text) -> List[Entity]` (core.py:50); use `.text` for Jaccard entity-set overlap.
- `svo.core.extract_svo(text) -> List[SVO]` (core.py:46); SVO has `.subject/.verb/.object` (head token text, may be None) for structural-overlap Jaccard/partial match.
- `negation_detector.core.detect_negations(text, window=5) -> List[Token]` (core.py:44); `.is_negated` flag. Used for polarity-mismatch metadata (does NOT enter composite score, per spec).
- `positive_signal_scorer/composite_scoring.py::composite()` (line 33) — composite-scoring pattern, ported (not imported) per isolation contract.
- `document_dispatcher` — exists (composition precedent).

### No fictional tools, no wrong schemas, no missing APIs. This spec is buildable as written.

## Caveats / things the build must handle (all noted in the spec itself or here)
1. **spaCy is venv-only.** `ner`/`svo`/`negation_detector` load `en_core_web_sm` independently; bare `python` has no spaCy (same dual-Python situation as torch for MTR). The gate's `RuntimeError` on missing spaCy is correctly specified (fail-loud). **All gate tests MUST run under `.venv/Scripts/python.exe`** — confirmed the `tools/run_TEST.py` runner is stdlib-only and does NOT activate `.venv`, so it must be invoked as `.venv/Scripts/python.exe tools/run_TEST.py`.
2. **`relevance_gate` not yet in `run_TEST.py` OWNED_PACKAGES** (tools/run_TEST.py:37-42). The build adds `"relevance_gate"` so the canonical runner discovers it. (Mirrors how `multispectral_analyzer` was added.)
3. **Gate wiring into `query_orchestrator_posix.py` is a SEPARATE, UNSPECIFIED ticket** (spec explicitly says so; companion proposal §6 step 4 calls it "a separate small spec"). This audit/build covers only the standalone tool (proposal Step 1). Wiring waits for Isaac's §5.1–5.3 decisions.
4. **`margin_threshold`/`volume_threshold` ship as placeholders** (0.15 / 8) per spec Non-Goals; flagged for recalibration against real candidate-set sizes. Not calibrated on synthetic data.
5. **Small-corpus IDF caveat** (5–20 facts typical): documented, not patched (per spec Implementation Notes).

## Build plan (proposal Step 1, this session)
- `tools/relevance_gate/`: `gate_schema.py` (CandidateFact, DimensionScores, ScoredCandidate, GateResult), `core.py` (`score_candidates`, `is_ambiguous`, `apply_relevance_gate`), `cli.py`, `__init__.py`, `__main__.py`, `README.md`.
- `TEST-relevance_gate_examples.json` covering the 6 minimum cases in the spec's Testing Strategy.
- Add `"relevance_gate"` to `run_TEST.py` OWNED_PACKAGES.
- Verify under `.venv`: runner + an ad-hoc gate. Commit-per-step.

## Relation to the broader drift
The proposal correctly diagnoses BitNet's cascade-role drift and is self-aware about its open questions (§5.1–5.4). The Relevance Gate (this spec) is the low-risk, inert-until-wired piece; the LLM-swap + BitNet-retirement are gated on Isaac's decisions and are OUT of scope for this build.
