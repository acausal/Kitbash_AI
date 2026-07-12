# SPEC: Observer Fail-Loud Violation Emission + Deterministic Fact Attribution

**Date:** 2026-07-12
**Baseline commit:** `d597ce0` or later (verify with `git log -1` before starting; STOP if learning_observer.py has changed since — re-read it, then report before proceeding)
**Parent findings:** 2026-07-12 code review, findings 2 (silent `except: pass`) and 4 (nondeterministic `returned_fact_id`)
**Socket map cells:** §2 LearningObserver (GREEN — must stay GREEN), §3 Dream Bucket write (GREEN — must stay GREEN)

---

## Context (read, do not act on)

`learning_observer.py` (~line 171–186): on MTR dissonance (`mtr_error > 0.5`)
the observer calls `dream_bucket.log_consistency_violation(...)` inside
`except Exception: pass`. Two silent failure modes:

1. Any exception in the emission path vanishes.
2. `writer.append(...)` returns `False` on queue backpressure — that bool is
   discarded, so a full queue also drops violations silently.

This is the same anti-pattern that has the MTR↔Grain bridge cell RED, sitting
on the one path whose job is surfacing dissonance. If violations stop flowing,
F2 recalibration silently starves — the `trace_logged=False` failure mode,
reincarnated.

Constraint that shapes the fix: a violation-write failure must NOT abort the
rest of `observe()` (feedback logging, phantom cadence, trace logging must
still run), and must NOT break answering. So the exception is still caught —
but recorded on the `LearningReport` and routed to the DiagnosticFeed by the
orchestrator, which owns the feed (single-owner rule; the observer has no feed
reference and must not gain one).

Secondly, ~line 178: `returned_fact_id=next(iter(fact_ids)) if fact_ids else 0`
picks an arbitrary member of a set. Set iteration order is not stable across
processes, so grain-side asymmetric feedback (Step 2) penalizes a different
fact on replay of identical inputs. Deterministic-first violation.

---

## Non-goals (touching any of these is a spec violation — STOP and report instead)

1. Do NOT change the dissonance gate (`mtr_error > 0.5`) or add any
   normalization/clamping of `mtr_error`. That is the signal-validation
   ticket (DIAGNOSTIC-trace_signal_check Q1), gated on Isaac's decision.
2. Do NOT give the observer a diagnostic-feed reference or any new ctor
   parameter. The orchestrator owns the feed.
3. Do NOT let a violation-emission failure raise out of `observe()` or alter
   `QueryResult` in any way. Answer path behavior is unchanged (telemetry
   only — no routing/answer approval gate is crossed by this spec).
4. Do NOT modify `dream_bucket.py`, `sleep_recalibration_service.py`, or the
   F2 test.
5. Do NOT create files beyond the deliverables named below.

---

## Deliverables

- Modified: `learning_observer.py`
- Modified: `query_orchestrator_posix.py` (one guarded block, telemetry only)
- Modified: `tests/TEST-learning_observer.py` (assertions ADDED; existing 7
  unchanged)

## Steps (in order)

### Step 1 — LearningReport fields

Add to the `LearningReport` dataclass:

```python
violation_emitted: bool = False          # a violation record was queued this query
violation_error: Optional[str] = None    # emission attempted but failed (exception or backpressure)
```

Both default-falsy so every existing consumer of `report.__dict__` is
unaffected when the gate never trips.

### Step 2 — Rewrite the emission block in `observe()`

Replace the current try/except-pass with:

```python
if mtr_error > 0.5 and self.dream_bucket_writer is not None:
    try:
        from dream_bucket import log_consistency_violation
        queued = log_consistency_violation(
            writer=self.dream_bucket_writer,
            source_layer="mtr",
            returned_fact_id=min(fact_ids) if fact_ids else 0,
            returned_confidence=mtr_confidence,
            mtr_error_signal=mtr_error,
            dissonance_type="high_confidence_low_coherence",
            context={"recent_fact_ids": list(self._recent_facts)},
        )
        if queued:
            report.violation_emitted = True
        else:
            report.violation_error = "writer.append returned False (queue backpressure)"
    except Exception as e:
        report.violation_error = f"{type(e).__name__}: {e}"
```

Notes:
- `min(fact_ids)` is the determinism fix (finding 4). One comment: smallest
  fact_id chosen for reproducibility; `result_summary` carries no
  primary/answering fact today — if it ever does, prefer it (leave that as a
  comment, not code).
- Execution continues past this block on failure — feedback logging, phantom
  cycle, and trace logging all still run. Do not reorder the pipeline.
- The `0` sentinel for empty `fact_ids` is retained (no grain maps to
  fact_id 0; recalibration treats it as unresolvable). Do not change it.

### Step 3 — Orchestrator surfaces the failure

In `query_orchestrator_posix.py`, immediately after the
`learning_report = self.learning_observer.observe(...).__dict__` assignment
(inside the same existing try), add:

```python
if learning_report.get("violation_error"):
    self.feed.log_error(
        query_id, "LEARNING_OBSERVER",
        f"violation emission failed: {learning_report['violation_error']}",
    )
```

This reuses the exact T7 #5 loud-failure channel. The feed is already a no-op
stand-in when Redis is absent, so this cannot raise or slow the answer path.

### Step 4 — Extend TEST-learning_observer.py

Add three assertions (new test functions; do not touch the existing 7). All
need a stub MTR engine whose error_signal means `mtr_error > 0.5` to trip the
gate, and a stub writer:

1. **Fail-loud on exception:** writer whose `append` raises →
   `report.violation_error` is set AND `report.error is None` AND
   `report.trace_logged` reflects the trace path still having run (pipeline
   not aborted) AND `observe()` did not raise.
2. **Fail-loud on backpressure:** writer whose `append` returns `False` →
   `report.violation_error` mentions backpressure,
   `report.violation_emitted is False`.
3. **Determinism:** `result_summary["fact_ids"] = {9, 3, 5}` with a capturing
   stub writer → the emitted record has `returned_fact_id == 3`, and
   `report.violation_emitted is True`.

## DONE WHEN (paste executed output — reading is not verification)

1. `python tests/TEST-learning_observer.py` → all tests PASS: the original 7
   plus the 3 new (10/10 or however the runner counts them). Paste full
   output.
2. `python tests/TEST-orchestrator_contract.py` → still 23/23 PASS (report
   shape change is additive; this proves it).
3. One ad-hoc scriptlet (paste it + output): build an observer with a raising
   stub writer, call `observe()` once with a gate-tripping stub engine, print
   the returned report — shows `violation_error` populated, `error=None`,
   and no traceback.

## Same-commit obligations

- `SOCKET_MAP.md`: §2 LearningObserver cell gains one sentence — violation
  emission is now fail-loud (report fields + feed routing), fact attribution
  deterministic (`min(fact_ids)`), test count updated. Cell stays GREEN only
  because DONE WHEN #1 executed; if any test fails, cell flips RED in the
  same commit and work STOPS.
- Discoveries out of scope → commit-message note, not spec extension
  (scope-lock).

## HARD STOP

Report DONE WHEN output and stop. The signal-validation run
(DIAGNOSTIC-trace_signal_check over the live bucket) and the Stage 1.5 live
edge-graph build are separate tickets and are NOT authorized by this spec.
