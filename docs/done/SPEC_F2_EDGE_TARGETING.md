# SPEC: F2 Edge-Targeting — Test Harness Repair + Mapping Implementation

**Date:** 2026-07-12
**Baseline commit:** `0978672` (verify with `git log -1` before starting; STOP if HEAD differs)
**Parent specs:** `docs/done/SPEC_AXIOM_RECALIBRATION.md` (F2, Step 1), `PROPOSAL_VIOLATION_SCHEMA.md` (approved)
**Socket map cell:** §5 "GAP — Violation records carry no edge/fact-chain reference" (currently YELLOW, follow-up (b))

---

## Context (read, do not act on)

Commit `0978672` landed the schema half of F2: `LearningObserver` now emits
violations with `context={"recent_fact_ids": [...]}`. The consumption half is
still the guarded no-op in `sleep_recalibration_service.py::_update_edge_weights`
(returns `targeting_field_present_but_mapping_unimplemented`, 0 edges changed).

`tests/TEST-recalibration_f2_targeted.py` is the RED-by-design contract for the
mapping. **It has a structural defect:** it builds the edge graph as a local
Python dict, never hands it to the service (not as an argument, not via disk),
then asserts the local dict changed. The real service reads and writes
`<dream_bucket_dir>/indices/procedural_edge_graph.json` via `_load_edge_graph()`
/ `_save_edge_graph()`. As written, NO implementation of
`_update_edge_weights(updates, violations)` can turn the test green.

Therefore: **Phase 1 repairs the test harness (assertions unchanged), Phase 2
implements the mapping.** Phase 1 must complete and be reported before Phase 2
begins. Do not combine them into one commit.

---

## Non-goals (touching any of these is a spec violation — STOP and report instead)

1. Do NOT modify `learning_observer.py` (the emission side is done; the
   `except: pass` and gate-calibration issues there are separate tickets).
2. Do NOT weaken, remove, reorder, or add tolerance to the four assertions in
   the F2 test. The fixture plumbing changes; the contract does not.
3. Do NOT change the public signature of
   `_update_edge_weights(updates, violations)`.
4. Do NOT run `run_recalibration_cycle()` against the live dream bucket
   (`data/subconscious/dream_bucket/`). All execution in this spec happens
   against temp-dir fixtures. Live consumption is gated on the mtr_error
   signal-validation ticket (DIAGNOSTIC-trace_signal_check Q1) — not this spec.
5. Do NOT create files beyond those named in the Deliverables lines below.
6. Do NOT invent targeting heuristics for violations that lack
   `context.recent_fact_ids`. Untargetable violations change nothing (that
   behavior already exists — preserve it).

---

## Phase 1 — Repair TEST-recalibration_f2_targeted.py

**Deliverable:** modified `tests/TEST-recalibration_f2_targeted.py` only.

### Steps (in order)

1. In `main()`, create a temp dream-bucket root (`tempfile.mkdtemp()` or
   `TemporaryDirectory`), construct
   `svc = RecalibrationService(dream_bucket_dir=<tmp>)`.
2. Write the existing 3-edge `_build_graph()` dict to
   `<tmp>/indices/procedural_edge_graph.json` (create the `indices` dir;
   plain `json.dump` is fine — this is fixture setup, not the atomic path).
3. Take the `before` snapshot by **reading that JSON back from disk**.
4. Call `svc._update_edge_weights(updates, [violation])` exactly as now
   (same `updates` dict, same violation record with the nested
   `context.recent_fact_ids` shape — do not flatten it).
5. Take the `after` snapshot by **re-reading the JSON from disk**.
6. Leave the four assertions byte-for-byte identical:
   - edge `1->3` CHANGED
   - edge `2->4` CHANGED
   - edge `9->10` UNCHANGED
   - `updated_count == 2`
7. Update the module docstring: fixture is now disk-based; RED/GREEN meaning
   unchanged.
8. Clean up the temp dir in a `finally`.

### DONE WHEN (paste executed output — reading is not verification)

- `python tests/TEST-recalibration_f2_targeted.py` executed; output shows the
  stopgap's `targeting_field_present_but_mapping_unimplemented` status, failure
  on the `edge 1->3 ... CHANGED` assertion, and **exit code 1**. The test is
  still RED — via the disk path. If it goes GREEN in Phase 1, something is
  wrong: STOP and report.

### HARD STOP

Report Phase 1 output. Commit Phase 1 alone
(suggested message: `F2 Phase 1: disk-based fixture for TEST-recalibration_f2_targeted (assertions unchanged, still RED)`).
Await go-ahead before Phase 2 unless Isaac has pre-authorized continuous
execution of this spec.

---

## Phase 2 — Implement the field→edge-key mapping

**Deliverable:** modified `sleep_recalibration_service.py` only.

### Behavior contract for `_update_edge_weights(updates, violations)`

1. **Partition violations.** Targetable = violation has a non-empty
   `context.recent_fact_ids` list (the nested shape the observer emits).
   Everything else is untargetable and contributes nothing. Replace the broad
   `EDGE_TARGET_FIELDS` sniff with this single check — the schema is now
   ratified; speculative field names (`edge_key`, `recent_facts`, etc.) come
   out. If NO violation is targetable, keep the existing no-op-and-report
   behavior (reason `no_edge_targeting_field_in_violations`).
2. **Load the graph** via the existing `_load_edge_graph()`. If it returns
   `None` (absent/corrupt), no-op with `reason: 'no_edge_graph_on_disk'`,
   `edges_updated=0`. Never fabricate a graph.
3. **Resolve incident edges.** For each targetable violation, an edge is
   implicated iff `edge['source_fact_id']` OR `edge['target_fact_id']` is in
   that violation's `recent_fact_ids`. Match on the record fields, not by
   parsing the `"src->tgt"` key string.
4. **Apply penalty** only to implicated edges with
   `confidence_mutable == True`:
   - Per violation per edge: `penalty = min(v['mtr_error_signal'] * EDGE_PENALTY_RATE, EDGE_PENALTY_CAP)`
   - Module-level constants: `EDGE_PENALTY_RATE = 0.15`,
     `EDGE_PENALTY_CAP = 0.1` (mirrors the grain-side Step 2 formula; one
     comment noting the mirror).
   - Multiple violations implicating the same edge accumulate, but the total
     decrement per edge per cycle is also capped at `EDGE_PENALTY_CAP`.
   - `edge_weight = max(0.0, edge_weight - total_penalty)` — floor at 0.0,
     never delete an edge (non-destructive archival principle).
   - Ignore the `updates` parameter for penalty math; penalties derive from
     violations. Note this in the docstring (param retained for signature
     stability at the `run_recalibration_cycle` call site).
5. **Persist** via the existing `_save_edge_graph()` (atomic tmp+replace). If
   save fails, report `action: 'failed'`, `reason: 'edge_graph_save_failed'` —
   do not claim success.
6. **Return** `(updated_count, status)`; `updated_count` = number of DISTINCT
   edges whose weight actually changed. Status dict includes at minimum:
   `action`, `violations_seen`, `violations_targetable`, `edges_implicated`,
   `edges_updated`, `edges_skipped_immutable`.
7. Rewrite the STOPGAP docstring to describe the implemented behavior; keep
   one line of history pointing at the old blanket-penalty bug and this spec.

### DONE WHEN (paste executed output for ALL of the following)

1. `python tests/TEST-recalibration_f2_targeted.py` → **exit 0**, all four
   checks ✓, `updated_count=2`, edge `9->10` weight unchanged on disk.
2. `python tests/TEST-recalibration_grain_step2.py` → still 16/16 PASS
   (no grain-side regression).
3. One ad-hoc REPL/scriptlet run (paste it): call `_update_edge_weights` with
   an **untargetable** violation (no `context`) against the same fixture →
   0 edges changed, no-op reason reported, graph file byte-identical.

### Same-commit obligations (map-maintenance rule 1)

- `SOCKET_MAP.md` §5 violation-schema cell: record that follow-up (b) is
  CLOSED (mapping implemented, F2 test GREEN, paste-reference the run);
  follow-up (a) (`procedural_edge_graph.json` absent on disk — Stage 1.5 must
  run over live traces) remains OPEN; cell stays YELLOW until (a) lands and
  the signal-validation gate clears.
- If anything out of scope is discovered, file it as a discoveries note in the
  commit message — do not extend this spec (scope-lock).

### HARD STOP

Report Phase 2 output and stop. Next steps (fail-loud pass on the observer,
signal validation, Stage 1.5 run) are separate tickets and are NOT authorized
by this spec.
