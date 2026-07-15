# 2026-07-15 — MTR profiling, L5 observation logger, Error Categorization

Three analysis/observation tools built this session (all core, repo root; not `tools/`).
Each: built, verified ad-hoc, committed, pushed. No `SOCKET_MAP.md` exists in repo
(flagged — README no longer asserts its presence).

## 1. MTR v6.1 Profiling + Contract Checks  (`cde7d14`)
- `mtr_profiler.py`: constructs production `KitbashMTREngine` (vocab 50257 / d_model 256 /
  d_state 144 — engine DEFAULT d_state=128 is NOT a perfect square and would crash; factory
  overrides to 144), measures init + `forward()` + `get_epistemic_snapshot()` latency, asserts
  5 contracts (latency bounds are explicit placeholders; snapshot-keys==LAYER_NAMES;
  DissonanceSensor no-KeyError).
- Behavioral contract suite `tests/TEST-MTR_v6_1_contract.py` RAN: **10/10 PASS** under `.venv`.
- Measured (CPU, torch 2.13+cpu): init ~190ms, forward p50 ~23ms / p95 ~27ms, snapshot p50 ~19ms.
- Caveats: must run under `.venv` (bare `python` has no torch → profiler exits 2, clean blocker,
  never fakes green). `tools/run_TEST.py` does NOT cover `/tests/*.py` or `mtr_profiler.py`.

## 2. L5 Observation Logger  (`7f7bbe7`)
- `l5_observation_logger.py` + wiring in `query_orchestrator_posix.process_query`.
- Non-acting: records per-query signals the LIVE orchestrator exposes (query, winning engine,
  confidence, latency, triage layer_sequence, turn, timestamp) + forward-compat `hat`/`topic`/
  `session_id` from `context` (None when absent — never fabricated). `summarize()` over JSONL.
- Caveats: logger unit-tested standalone (real). Orchestrator *wiring* py_compile-clean but NOT
  executed end-to-end (needs engines running). Live orchestrator does NOT compute hat/topic
  (retired `attic/query_orchestrator.py` only; Mamba/L4-L5 off here).

## 3. Error Categorization  (`120371d`) — REDESIGN on real schema
- `error_categorizer.py`. Spec `PIPELINE-ERROR_CATEGORIZATION_FOR_SPECIALISTS.md` assumed
  `user_complaint`/`context_at_failure`/`grain_confidence` + tools `log_parser` /
  `conditional_pattern_detector` / `pattern_explainer` / `text_search.match_any` — NONE exist.
- Real record (`dream_bucket.log_consistency_violation`) = `dissonance_type` / `returned_confidence`
  / `mtr_error_signal` / etc., no complaint text. Categorizer uses real fields; spec's 8 NL
  categories (coreference, sense ambiguity, ...) intentionally NOT fabricated (report states it).
- Verified END-TO-END on REAL synthetic violations (`generate_synthetic_dream_bucket` → categorizer
  via `DreamBucketReader`): all records categorized, report produced.
- Caveat: real-data run pending real query violations.

## What was NOT done
- E2E B1 verify: DEFERRED — BitNet :8080 + Redis :6379 down; user investigating schema/code drift.
- Microspecialist selection / LoRA / SLM-v3 3.5 / handshake harness: still blocked on data/research
  (per original list).
- `tools/run_TEST.py` not extended to cover `/tests/*.py` or the new core profiler/logger/categorizer.
