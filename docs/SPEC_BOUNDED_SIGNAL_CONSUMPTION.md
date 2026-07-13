# SPEC: Bounded Signal Consumption — Raw Records, Squashed Decisions

**Date:** 2026-07-13
**Baseline commit:** `0a7bc27` or later (verify with `git log -1`; if the
trace-chain spec has landed first, that is fine — STOP only if
`learning_observer.py` or `sleep_recalibration_service.py` changed outside
these two specs)
**Parent findings:** Task B signal readout (live `mtr_error_signal` up to
8.77, confidence to −8.6; gate `>0.5` admits ~everything; penalty caps at
raw ≥ 0.67)
**Isaac's ratified decision:** records keep RAW values (ground truth,
non-destructive); all DECISIONS (gate trip, penalty magnitude) operate on a
bounded transform. The actual discrimination threshold is DEFERRED —
resume trigger: after a body of real (non-synthetic) usage sessions exists,
re-pick empirically from the live distribution. Percentile-based gating is
the documented alternative at that point.

---

## Non-goals (touching any of these is a spec violation — STOP and report instead)

1. Do NOT change what is WRITTEN to any record: `mtr_error_signal`,
   `returned_confidence`, trace `confidence` all stay raw.
2. Do NOT pick a new threshold, add percentile logic, or otherwise attempt
   discrimination improvements. This spec is plumbing; the default behavior
   must be IDENTICAL to today (see equivalence note below).
3. Do NOT touch the chain/extractor path (companion spec) or run anything
   against live data beyond the read-only DONE WHEN item.
4. Do NOT create files beyond the deliverables named below.

---

## Deliverables

- New: `signal_transforms.py` (module root, alongside the other services)
- New: `tests/TEST-signal_transforms.py`
- Modified: `learning_observer.py` (gate reads the transform)
- Modified: `sleep_recalibration_service.py` (penalty input reads the
  transform)

## Steps (in order)

1. **`signal_transforms.py`** — small and boring on purpose:

   ```python
   # Operational knobs (module constants per codebase convention).
   # GATE_THRESHOLD deliberately unchanged from the historical 0.5 —
   # re-picking it is the deferred calibration decision, resume trigger
   # documented in SPEC header.
   GATE_THRESHOLD: float = 0.5

   def bounded_error(raw: float) -> float:
       """Clamp raw mtr_error into [0.0, 1.0] for decision-making.
       Records always store raw; only decisions consume this. Chosen over
       sigmoid for explainability: the live distribution (Task B readout,
       2026-07-13) shows raw values to ~8.8, and no smooth transform
       recovers discrimination from an uncalibrated signal — that is the
       deferred threshold decision, not this function's job."""
       return max(0.0, min(1.0, raw))

   def gate_trips(raw_error: float) -> bool:
       return bounded_error(raw_error) > GATE_THRESHOLD
   ```

2. **Observer:** the dissonance check `mtr_error > 0.5` becomes
   `gate_trips(mtr_error)`. The violation record still writes RAW
   `mtr_error` and RAW `mtr_confidence`. One comment pointing at this spec.
3. **Recalibration:** every penalty computation that consumes
   `mtr_error_signal` (grain-side Step 2 AND the F2 edge-side) wraps it:
   `penalty = min(bounded_error(v["mtr_error_signal"]) * RATE, CAP)`.
   RATE/CAP constants unchanged.
4. **Equivalence note (assert it, don't assume it):** for all raw ≥ 0,
   `clamp(x) > 0.5 ⇔ x > 0.5`, and for the penalty,
   `min(clamp(x)*0.15, 0.1) == min(x*0.15, 0.1)` for every x that trips the
   gate (both cap at x ≥ 0.67; below 0.67 clamp is identity). Default
   behavior is therefore byte-identical today. Negative raw inputs (seen
   live on confidence-derived paths) now clamp to 0.0 instead of producing
   negative penalties — the ONLY behavioral delta, and it is a bug-fix
   direction (a negative penalty would have REWARDED an edge on a
   violation).

5. **`tests/TEST-signal_transforms.py`**, minimum: clamp bounds (raw 8.77 →
   1.0; raw −7.77 → 0.0); gate equivalence at 0.45 / 0.5 / 0.51 / 8.77;
   penalty equivalence at raw 0.6 and raw 3.0; negative-raw penalty is 0.

## DONE WHEN (paste executed output for ALL)

1. `python tests/TEST-signal_transforms.py` → all PASS.
2. `python tests/TEST-learning_observer.py` → all PASS (gate behavior
   unchanged at defaults).
3. `python tests/TEST-recalibration_f2_targeted.py` → still GREEN, and
   `tests/TEST-recalibration_grain_step2.py` → still 16/16 (penalty
   equivalence proven by the existing suites, not by reading).
4. Read-only ad-hoc (paste it + output): map `bounded_error` over the live
   violations' raw `mtr_error_signal` values and print min/mean/max of the
   transformed distribution — the number Isaac will stare at when the
   threshold decision resumes.

## Same-commit obligations

- SOCKET_MAP §5 measured-signal note gains one line: decisions now consume
  `bounded_error()`; records raw; threshold re-pick deferred with named
  resume trigger (real-usage corpus).
- Discoveries → commit-message tickets, not scope extension.

## HARD STOP — report and stop. Threshold re-pick and any live Stage 5 run remain unauthorized.
