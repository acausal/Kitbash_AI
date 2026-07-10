# SPEC: Axiom-Aware Recalibration (Mutation 5 Correction)

**Date:** 2026-07-10
**Status:** APPROVED FOR IMPLEMENTATION — execute steps in order, no skipping
**Audience:** implementing model(s). Read the whole document before writing any code. Working rules apply: surgical edits, TEST-/DIAGNOSTIC- prefixes for non-shipping files, paste executed test output — claimed success is not success.
**Priority:** Ahead of `SPEC_DOCUMENT_ADDRESSING.md` in your queue — F2 below is a live correctness bug (not a missing feature), and this fix is small. Complete this before resuming that spec or before touching Redis bus / Mutation 1 wiring.
**Blocking:** nothing upstream. This is a correction to `sleep_recalibration_service.py`, which the socket map currently marks as complete (Mutation 5, STATUS_2026-06-04.md). That status is inaccurate against the file's actual behavior — see §1. Correcting the SOCKET_MAP.md note for this cell is part of this spec's acceptance criteria, not optional cleanup.

---

## 1. Current State (verified by direct read of `sleep_recalibration_service.py`, 2026-07-10)

The file's own docstring claims it "applies Dream Bucket feedback uniformly to grain confidences and edge weights." What it actually does is materially different from that claim in two directions — one better than the docstring implies, one worse:

**F1 — Grain confidence updates are a complete no-op.** `_update_grain_confidences` (lines 139–162) computes a penalty per grain key, then the actual write to the grain registry is commented out (lines 155–159: `# grain = grain_registry.get(grain_id) / # if grain.confidence_mutable: ...`). The method only increments a counter for the report and returns. **No grain confidence has ever been changed by this service.** This is better news than it sounds: there is no existing erosion behavior to preserve, and no regression risk on the grain side — this is first-time implementation, not a bug fix.

**F2 — Edge weight updates hit every edge in the graph, not just involved ones.** `_update_edge_weights` (lines 164–206) takes `statistics.mean(updates.values())` — the average penalty across *all* pending violations from this cycle — and applies that single averaged value to *every edge in `procedural_edge_graph.json`*, gated only on `confidence_mutable` (which defaults `True` for all edges). The code comments admit this: *"Apply general penalty (errors affect all edges uniformly) — More sophisticated: could track which edges were involved"* (lines 187–188). **This is live and currently running**: every sleep cycle with any violations at all degrades every edge in the graph (~1,200+ at last count), regardless of relevance. This is the one actively causing damage — fix it first within this spec if you need to sequence internally.

**F3 — No fact→grain resolution exists.** Grain penalties are keyed by a synthetic string, `f"grain_from_fact_{returned_id}"` (line 127) — not an actual `grain_id` lookup. **Verify before building anything else**: a prior session's grain-router investigation found that on-disk grain files carry no `fact_id` field at all (`grain_by_fact` index came back empty). If that's still true, a fact→grain mapping may not be constructible from current on-disk grain data, and this spec's grain-side work is blocked on a data format gap, not a logic gap. Check this first (§4 Step 0) before writing any grain-side code.

**F4 — No contradiction severity gate, no reconciliation path.** `_read_violations` (lines 212–239) filters only on `mtr_error_signal > 0.3` — a single continuous threshold, no distinction between ambient noise and an actual hard contradiction between new and existing knowledge. There is no `grain_type` check anywhere in the file (axiom vs. observation), and no path that flags anything for review rather than directly penalizing it. `DREAM_BUCKET_DESIGN.md` already specifies a `hypothesis` subtype called `"contradiction"` (Category D) — this exists in the design and the schema, but nothing currently writes or consumes it.

## 2. Target Architecture

### 2.1 Fact→grain resolution (prerequisite to 2.2 — contingent on §4 Step 0's finding)

If grain files can be made to carry `fact_id` (or already do and the prior finding was specific to a subset), build a real `fact_id → grain_id` lookup, sourced from `grain_registry.py`. If the prior finding holds and grain files fundamentally lack this, **stop and report** — do not invent a workaround (e.g., guessing via content matching) without asking first. This may mean grain-side recalibration is deferred pending a grain schema change, tracked separately, while edge-side (F2) proceeds independently — the two are not coupled and F2 should not wait on F3's resolution.

### 2.2 Axiom/observation asymmetry (grain side, contingent on 2.1)

Per `KITBASH_ROADMAP_MAY_2026.md`'s original Mutation 5 design, not the uniform version that shipped:

```python
if grain.grain_type == "observation":
    grain.confidence = max(0.0, grain.confidence - (dream_bucket_signal * 0.15))
elif grain.grain_type == "axiom":
    if dream_bucket_signal > AXIOM_CONTRADICTION_THRESHOLD:  # concrete value set in §4 Step 2, not guessed here
        # Do NOT decrement directly. Flag instead:
        log_hypothesis(
            writer,
            hypothesis_subtype="contradiction",
            entities=[grain_id],  # or relevant fact_ids per grain
            hypothesis_text=f"Grain {grain_id} (axiom) contradicted by new evidence, signal={dream_bucket_signal}",
            confidence=dream_bucket_signal,
            evidence=[...],  # violation record references
            generated_by="recalibration_service",
        )
        # No confidence change here. A downstream sleep stage consumes
        # this hypothesis and runs the actual reconciliation pass (§2.4).
```

Axioms below the contradiction threshold get **no confidence change at all** — ambient noise should not erode an axiom incrementally the way it can erode an observation. This is a real behavioral difference from observations, not a smaller version of the same penalty.

### 2.3 Targeted edge penalties (edge side, independent of 2.1/2.2 — fix this first if sequencing internally)

Replace the "average penalty applied to every edge" logic with penalties applied **only** to edges actually implicated by a violation. This requires the violation record to identify which edge(s) were involved — check what's actually recoverable from `context` in a `consistency_violation` record (`DREAM_BUCKET_DESIGN.md` Category C shows `recent_facts` in context; confirm whether that's sufficient to resolve to specific edge keys, or whether the violation schema needs a new field). If violations genuinely don't carry enough information to target specific edges, **stop and report** — do not fall back to the current "penalize everything" behavior silently, and do not guess at a targeting heuristic without confirming it's sound.

### 2.4 Reconciliation pass consumption

A sleep stage (Stage 3 — Hypothesis Generation, or a new sub-stage — decide and justify in §4 Step 4) reads `hypotheses.jsonl` for `hypothesis_subtype == "contradiction"` entries, and runs an actual reconciliation check: does the new evidence hold up against re-examination, or was it noise? Outcome determines whether the axiom gets demoted (to observation, or a lower-confidence axiom) or the hypothesis gets discarded. This is a decision-and-report step, not silent — every reconciliation outcome should be logged with its reasoning, consistent with the project's existing audit-trail expectations (`l2_working_theory_service.py`'s read-only audit pattern is the model to follow, not reinvent).

## 3. Design Constraints (do not violate these while implementing)

- **No new Dream Bucket log type.** Use the existing `hypotheses` log type with `hypothesis_subtype="contradiction"` — this is already in `DREAM_BUCKET_DESIGN.md`'s schema, just unwired. Do not add to `dream_bucket.py`'s `valid_types` set; that's a shared enum other things depend on and extending it is out of scope here.
- **Edge fix (F2) and grain fix (F1/F3/F4) are independent.** Do not let one block the other. If §4 Step 0 finds the grain-side fact→grain mapping is genuinely blocked, ship the edge-side fix alone and report the grain-side blocker separately rather than stalling everything.
- **This touches a socket the map currently marks GREEN.** Treat this as a correction to an existing, supposedly-complete component, not new work — the socket map update (§4 Step 5) must be explicit that the prior GREEN status was based on the file's docstring/uniform-treatment framing rather than verified behavior, so the maintenance-rule lesson is visible in the map itself, not just in this spec.

## 4. Build Checklist (strict order; acceptance criteria are executed test output)

**Step 0 — Verify the fact→grain data gap (F3).**
Check whether grain files on disk currently carry a `fact_id` field, re-confirming or updating the prior grain-router-session finding. Report the result before writing any grain-side code.
*Acceptance:* concrete finding pasted (field present/absent, sample grain file shown), with a recommendation: build the mapping now, or flag as blocked and proceed edge-side-only.

**Step 1 — Fix F2 (edge targeting) first — it's the live bug.**
Determine what's recoverable from violation records to target specific edges (§2.3). Implement targeted penalty application, replacing the "average penalty to every edge" logic.
*Acceptance:* new/updated test demonstrating: a violation implicating edge X applies a penalty to X and does NOT change the weight of unrelated edge Y. Paste executed output. If violation records don't carry enough information to target specific edges, report this finding instead of proceeding with a guess.

**Step 2 — Implement grain-side write-back with axiom/observation asymmetry (F1, F4, §2.2) — contingent on Step 0.**
If Step 0 confirms the mapping is buildable: implement the actual grain registry write (finally uncommenting and correctly implementing what was stubbed at lines 155–159), with the axiom/observation branch. Set a concrete `AXIOM_CONTRADICTION_THRESHOLD` value and justify it (don't invent an arbitrary number silently — propose one with reasoning, e.g. relative to the existing `mtr_error_signal > 0.3` violation-inclusion threshold, and flag it for review).
*Acceptance:* test demonstrating: an observation grain's confidence decrements on a moderate signal; an axiom grain's confidence does NOT change on that same moderate signal; an axiom grain triggers a `log_hypothesis(..., hypothesis_subtype="contradiction")` call on a signal above threshold, and still does not have its confidence directly changed by this service.

**Step 3 — Reconciliation consumption (§2.4).**
Wire a sleep stage to read `contradiction` hypotheses and produce a reconciliation decision (demote / discard) with logged reasoning.
*Acceptance:* end-to-end test: synthetic contradiction hypothesis in `hypotheses.jsonl` → sleep stage runs → produces a decision record with reasoning, output pasted.

**Step 4 — Decide reconciliation's home.**
Confirm whether reconciliation lives in existing Stage 3 (Hypothesis Generation) or a new sub-stage (precedent: Stages 1.5/2.5/5.5 were added as cosmetic sub-stage insertions elsewhere in this pipeline — follow that pattern if a new stage is warranted rather than overloading Stage 3's existing contract). State the decision and reasoning before Step 3's wiring is finalized, not after.
*(Acceptance folded into Step 3's.)*

**Step 5 — Correct the socket map.**
Update the Mutation 5 / recalibration cell(s) in `SOCKET_MAP.md` to reflect verified current behavior post-fix, and add a note on why the prior GREEN status was wrong (docstring claimed uniform treatment; actual prior behavior was no-op-on-grains + untargeted-on-edges).
*Acceptance:* diff or excerpt of the updated SOCKET_MAP.md section pasted.

## 5. Contract Test Specification (for a permanent `TEST-recalibration_contract.py`)

Minimum assertions once Steps 1–3 are complete:
1. Edge targeting: implicated edges change weight, unrelated edges do not, for a given violation set.
2. Grain asymmetry: observation grains decrement on moderate signal; axiom grains do not decrement on the same signal, but do produce a contradiction hypothesis above threshold.
3. No confidence change on any axiom grain from this service, ever — confirm this holds even under a batch of many moderate-signal violations (ambient noise should never accumulate into an axiom demotion via this path; only the explicit reconciliation decision in Step 3 may change an axiom's status).
4. Reconciliation stage produces a decision record with reasoning for every contradiction hypothesis it consumes — no silent drops.
5. If Step 0 found the grain-side mapping blocked: a test confirming the edge-side fix works correctly in isolation, with grain-side code paths absent or clearly stubbed-and-reported rather than silently broken.

## 6. Out of Scope

No changes to the MTR Ebbinghaus decay mechanism (`MTR_v6_1.py`) — that's already correctly scoped to transient L2 working-theory state and is not part of this bug. No changes to `dream_bucket.py`'s `valid_types` enum. No work on Redis bus wiring, Mutation 1, or Mutation 2 — unrelated tracks, do not let this spec's completion become a reason to start pulling those in. No document-addressing work (`SPEC_DOCUMENT_ADDRESSING.md`) until this spec is complete, per the priority note at the top.

---
*Written against a direct read of `sleep_recalibration_service.py` as of 2026-07-10. If that file has changed since, re-verify §1's line references before executing Step 0.*

## Appendix — Partial-closeout note (2026-07-10, executed as Option 1)

**Scope actually completed this session:** Step 0 (F3 gap verified — grains lack `fact_id` AND `grain_type`), Step 1 only in its STOPGAP form (F2 blanket-penalty neutralized to guarded no-op-and-report; real edge targeting still blocked on the violation-schema gap), Step 5 (SOCKET_MAP + STATUS corrected). Steps 2–3 (grain write-back with asymmetry, reconciliation consumption) NOT done — blocked on the two schema gaps.

**Two blockers (verified):**
- Grain schema gap: `grains/*.json` carry no `fact_id`, no `grain_type` (only `epistemic_level`). Blocks F1/F3/§2.2. Owner = Mutation 1 schema change.
- Violation schema gap: `violations.jsonl` keys `[dissonance_type, mtr_error_signal, returned_confidence, returned_fact_id, session_id, timestamp]` — no `context`/`recent_facts`/edge ref. Blocks real F2 targeting.

**Urgency correction:** F2 was believed live-damaging; `procedural_edge_graph.json` does not exist, so `_update_edge_weights` returned early and changed nothing. Latent bug, not active. Re-check for an edge graph before assuming live damage if this resurfaces.

**Revisit trigger:** when grain schema gains `fact_id`+`grain_type` OR violation schema gains an edge/fact-chain ref, Steps 2–3 unblock. See STATUS_2026-07-10.md "Mutation 5 Recalibration spec — CLOSED PARTIAL" section.
