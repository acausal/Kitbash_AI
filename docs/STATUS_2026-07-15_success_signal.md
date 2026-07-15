# STATUS: Success Signal Integration — Implementation Log

**Date:** 2026-07-15
**Spec:** `docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md` (Status: Ready for Implementation)
**Deviation audit:** `docs/DEVNOTE-SUCCESS_SIGNAL_INTEGRATION.md`
**Scope:** Core infrastructure (Dream Bucket + Query Orchestrator) — NOT `tools/` sandbox

## Current state (as of this log)

### Implemented
- **`dream_bucket.py` (Deviation 2):**
  - `"success_traces"` added to `DreamBucketWriter.valid_types`.
  - Module-level `log_success(writer, response, grains, facts, metadata, session_id)` → `writer.append("success_traces", record)`.
  - `count_recent_violations(reader, hours=24)` → counts `violations` log entries since cutoff.
  - `read_success_traces(reader, limit=100)` → recent success traces, newest last.
  - Fixed a missing `timedelta` import surfaced by the ad-hoc verification gate.
- **`query_completion_heuristic.py` (NEW):** `CoherenceChecker` + `CoherenceCheckResult` + `COHERENCE_THRESHOLDS` + `generate_trace_id`, verbatim from spec. Pure-logic, no I/O, deterministic.
- **`query_orchestrator_posix.py` (Deviation 1, Step 3):**
  - Imported `DreamBucketWriter` + `CoherenceChecker`/`generate_trace_id` (graceful degrade on ImportError).
  - `__init__` lazily creates a non-blocking `DreamBucketWriter("dream_bucket")` as `self._success_writer`.
  - Hook after line 333 (post `answer`/`confidence`, pre `return`): runs `CoherenceChecker().check(violations_count=0, top_grain_confidence=confidence, response_length=len(answer.split()), parse_errors=[])`; on pass, `log_success(...)` with provenance pulled from `winning_response.metadata` (`fact_id`/`grain_id`). Fully guarded in try/except (logging failure never blocks answering).
  - `close()` now also flushes `self._success_writer` so queued success traces persist.
- **Verification:** ad-hoc gates passed — success trace round-trips via real `DreamBucketWriter`; Step 3 block verified against a real writer (126-word answer → coherence pass → trace lands, flushes, reads back). Three re-fires, all green. `query_orchestrator_posix.py` parses + imports cleanly.
- **Commits:** `d4a6938` (Steps 1–2), `0e8057b` (docs batch), Step 3 is this commit.

- **THRESHOLD DEFECT (RESOLVED 2026-07-15, this session):** the spec's fixed `min_response_length=100` words falsely rejected legitimate short answers. Replaced with a query-aware dynamic threshold (`compute_dynamic_min_length` in `query_completion_heuristic.py`): factual (is/are/what/who/where/when) base 5, explanation (explain/how/why/describe) base 60, other base 30; high confidence (≥0.85) ×0.7, low (<0.60) ×1.3. `CoherenceChecker.__init__` now takes `min_response_length: int | Callable | None` — None (default) = dynamic, int = legacy fixed, callable = custom. `check()` gained a `query` param; `CoherenceCheckResult` gained `dynamic_min_length_used`. Orchestrator passes `query=user_query`.
  - **DEVIATION from the resolution doc:** its table listed factual base = 20, but its own test (`test_coherence_checker_short_factual_answer`) asserts a 5-word factual answer passes — contradictory (20 would fail 5). To satisfy the stated goal (short factual answers pass), factual base was set to **5**, not 20. All 4 resolution acceptance scenarios pass. Flagged, not silently hidden.
  - Legacy fixed mode and the spec's `min_response_length=100` are preserved (pass `min_response_length=100` to `CoherenceChecker`).
- **`slm success-stats` CLI:** deferred (manual `read_success_traces` suffices for Phase A).
- Violations path (`violations.jsonl`) is untouched. `violations_count` is hard-coded 0 per user decision A (clean answered query) — semantic violation counting from `learning_observer` is not yet wired (post-1.0).

## Honesty note
All three steps are executed-and-verified (ad-hoc gates), not merely wired. The full orchestrator was NOT run end-to-end (requires BitNet/Mamba engine stack); verification targets the exact code paths added. The threshold caveat above is a real, unverified-in-production concern.

### Deviations from spec (resolved vs open)
- Orchestrator target name: spec said `query_orchestrator.py`; actual is `query_orchestrator_posix.py` (donor retired to `attic/`). Hook located at ~line 333. **RESOLVED (Step 3 landed this session).**
- `structured_logger.get_event_logger(...).log(...)` calls in spec: API confirmed correct against `structured_logger.py`. **No change needed.**
- `slm success-stats` CLI: deferred (manual `read_success_traces` suffices for Phase A). **Open, deferred.**
- Non-blocking writer gotcha: `DreamBucketWriter` queues via background thread; callers must `close()` at shutdown or queued traces are lost. **HONORED (orchestrator.close() flushes `self._success_writer`).**

## Honesty note
All three steps are executed-and-verified (ad-hoc gates), not merely wired. The full orchestrator was NOT run end-to-end (requires BitNet/Mamba engine stack); verification targets the exact code paths added. The threshold caveat above is a real, unverified-in-production concern.
