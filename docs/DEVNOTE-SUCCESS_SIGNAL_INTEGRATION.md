# DEVNOTE: SUCCESS_SIGNAL_INTEGRATION — Spec Deviation Audit

**Date:** 2026-07-15
**Spec:** `docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md` (Status: Ready for Implementation)
**Auditor:** Hermes (verified against repo at HEAD, not inferred)
**Scope classification:** Core infrastructure (Dream Bucket + Query Orchestrator) — **NOT `tools/` sandbox**
**Verdict:** Architecturally sound, but written against the pre-`attic/` repo layout. Spec prose diverges from current code in 3 places. All fixable; none are architectural errors.

---

## Assumptions VERIFIED against source (not guessed)

| Claim | Status | Evidence |
|---|---|---|
| `structured_logger.get_event_logger(name).log(event_type, data={})` | ✅ correct | `structured_logger.py:405` `get_event_logger` → `ComponentLogger.log` (line 357). Module is real (NOT a misnomer for `structured_validator`, which is only a SPEC doc). |
| `query_orchestrator.py` at repo root | ❌ does NOT exist | Retired to `attic/query_orchestrator.py` (STATUS_2026-07-10.md, T6 commit `f527b2c`). |
| Active orchestrators | ✅ | `query_orchestrator_posix.py` (class `QueryOrchestrator`) + `query_orchestrator_factory.py`. |
| `finalize_response()` | ❌ does NOT exist | Must be authored; hook point is `query_orchestrator_posix.py:~293-398` (post `answer`/`confidence` assignment, pre-return). |
| `dream_bucket.py` classes | ✅ | `DreamBucketWriter` / `DreamBucketReader` present (484 lines, not 482). |
| `dream_bucket/live/violations.jsonl` | ✅ | `DreamBucketWriter.append("violations", record)`; `valid_types` includes `"violations"`, `"traces"`, `"false_positives"`, `"collisions"`, `"hypotheses"`, `"pending_questions"`, `"validated_observations"`. |
| `log_success` / `count_recent_violations` / `read_success_traces` | ❌ do NOT exist | Must be added. Closest existing: `writer.append`, `reader.count_log_records(log_type)`, `reader.read_live_log(log_type)`, `reader.read_live_log_since(log_type, ts)`. |
| `slm` CLI / `success_signal_cli.py` | ❌ does NOT exist | Defer or build. |

---

## Deviation 1 — Orchestrator wiring target (MEDIUM risk, core pipeline)

**Spec says:** modify `query_orchestrator.py` → `finalize_response()`.
**Reality:** root `query_orchestrator.py` is retired; live code is `query_orchestrator_posix.py`.

**Hook point (verified):** in `QueryOrchestrator.execute_query` (or its wrapper), `answer` and `confidence` are assigned at lines 293–295; the result dict is assembled at 397–398 (`answer=answer, confidence=confidence`). That is the post-response, pre-return location for the coherence check.

**Action:** import `CoherenceChecker` (new `query_completion_heuristic.py`) + the dream_bucket convenience functions, instantiate `CoherenceChecker()`, call `.check(violations_count=..., top_grain_confidence=confidence, response_length=len(answer.split()), parse_errors=...)`, and on `passed` log a success trace. `confidence` is already available at the hook; `grains_activated`/`facts_used`/`edges_traversed` must be sourced from the orchestrator's own resolve state (verify field names at build time).

**Effort:** ~2.5h (0.5h locate/confirm hook, 1h wire + call, 1h e2e test).

---

## Deviation 2 — Dream Bucket missing methods (LOW risk, additive)

**Spec says:** `dream_bucket.log_success(...)`, `.count_recent_violations(hours=24)`, `.read_success_traces(limit=100)`.
**Reality:** none exist. The writer exposes `append(log_type, record)` (NOT `append_trace`), and `log_type` must be in a fixed `valid_types` set — `"success_traces"` is **not** in it, so either add `"success_traces"` to `valid_types` or call `writer.append(...)` directly. Existing convenience functions (`log_consistency_violation`, `log_trace`) take `writer` as first arg. Violations are logged via `log_consistency_violation(writer, ...)` → `append("violations", ...)` (there is **no** `log_violation`).

**Recommended shape (matches actual API):**
```python
# dream_bucket.py — additive, module level (no class refactor needed)
def log_success(writer, response, grains, facts, metadata=None):
    record = {
        "outcome": "success",
        "response": response,
        "grains_activated": [g.id for g in grains],
        "facts_used": [f.id for f in facts],
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return writer.append("success_traces", record)   # requires adding "success_traces" to valid_types

def count_recent_violations(reader, hours=24) -> int:
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    return sum(1 for _ in reader.read_live_log_since("violations", since))

def read_success_traces(reader, limit=100) -> list:
    return list(reader.read_live_log("success_traces"))[:limit]
```
**Note:** `DreamBucketWriter` is non-blocking (queued, background thread) — call `writer.close()` at process exit or queued success traces are lost. This is a real operational gotcha the spec doesn't mention.

**Effort:** ~2–3h (add + test).

---

## Deviation 3 — CLI tool does not exist (LOW risk, optional)

**Spec says:** `slm success-stats`.
**Reality:** no `slm` command and no `success_signal_cli.py`.
**Decision:** defer to post-data-collection (manual inspection via `reader.read_live_log("success_traces")` is sufficient for Phase A). Build only if it becomes analysis-blocking.

---

## Build order (lowest risk first)
1. **Deviation 2** — add 3 functions to `dream_bucket.py` (self-contained, additive).
2. **Deviation 1** — wire coherence check into `query_orchestrator_posix.py` hook (~293–398).
3. **Deviation 3** — skip unless asked.

## Files touched (core pipeline — outside `tools/` sandbox)
| File | Change | Risk | Effort |
|---|---|---|---|
| `dream_bucket.py` | add 3 functions (+ `"success_traces"` to `valid_types`) | Low | 2–3h |
| `query_orchestrator_posix.py` | add coherence-check hook | Medium | 2–3h |
| `query_completion_heuristic.py` | NEW (from spec `CoherenceChecker`) | Low | 1–2h |
| `success_signal_cli.py` | NEW (optional) | Low | 0h (defer) / 2h |

**Total:** 5–8h (excluding optional CLI).

## Open questions for the implementation session
1. Exact orchestrator field names for `grains_activated` / `facts_used` / `edges_traversed` at the hook (read the resolve state at build time).
2. Should `success_traces` be added to `DreamBucketWriter.valid_types`, or call `writer.append` directly with a hardcoded allow? (Recommend adding to `valid_types` for consistency.)
3. Coherence timing: immediately after `answer` is set (line ~295) per spec — confirmed correct.
4. CLI priority for Phase A: defer (recommended).

## Caveats on the prior draft
The earlier hand-drafted deviation note contained errors and was NOT saved: it reported `dream_bucket.py` as 482 lines (actual 484, conflated with `structured_logger.py`); it referenced a nonexistent `DreamBucketWriter.append_trace()` (actual: `append(log_type, record)`); it called a nonexistent `log_violation()` (actual: `log_consistency_violation(writer, ...)`); and its `reader.read_traces(...)` does not exist (actual: `read_live_log` / `read_live_log_since`). This note supersedes it with source-verified facts.

## Related
- `docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md` (original spec)
- `STATUS_2026-07-10.md` (documents `attic/` migration — source of Deviation 1)
- `SOCKET_MAP.md` (violations path cited as `data/subconscious/dream_bucket/live/`; code uses relative `dream_bucket/live/`)
