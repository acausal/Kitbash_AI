# SPEC: Orchestrator Reconciliation

**Date:** 2026-07-07
**Status:** APPROVED FOR IMPLEMENTATION — execute steps in order, no skipping
**Audience:** implementing model(s). Read the whole document before writing any code. Working rules apply: surgical edits, max two files per response, ask for any file you cannot see, TEST-/DIAGNOSTIC- prefixes for non-shipping files, paste executed test output — claimed success is not success.
**Blocking:** all three Phase 5 blockers (Mutation 1, Redis bus, Mutation 2). Nothing wires into the orchestrator until this spec is complete.

---

## 1. Current State (verified 2026-07-07 by direct audit)

Three orchestrators exist:

| File | Role | State |
|---|---|---|
| `query_orchestrator_posix.py` | CANONICAL. Interface-driven cascade (triage → GRAIN → CARTRIDGE), heartbeat, metabolism, resonance, diagnostic feed, coupling deltas. | Clean architecture; contains **none** of the Phase 3E+/5 learning machinery (3 grain-pipeline references vs 52 in the donor; zero L2/trace references). |
| `query_orchestrator.py` | DONOR. Monolithic Phase 3E+ pipeline: cartridge lookup → grain lookup → MTR inference → feedback logging → resonance → phantom tracking/crystallization → L2 init → procedural trace logging. | Contains the machinery to migrate, plus **five live bugs** (§2). Constructs all dependencies itself; not the factory path. |
| `phase3e_orchestrator.py` | LEGACY. Older revision of the donor. | Archive (§5, Step 0). |

**Finding F1 — the built-but-unplugged brain.** `query_orchestrator_factory.py` (the canonical entry) constructs `KitbashMTREngine`, `MTRStateCheckpoint`, `ShannonGrainOrchestrator`, `GrainRouter`, and `MTRGrainUnifiedPipeline` (lines ~109–157), logs each as initialized, then constructs the posix orchestrator **without passing any of them** — the posix constructor has no parameters for them. Only `shannon=grain_orchestrator` crosses over, feeding the thin `_record_phantom_hit` stub. The MTR engine, state manager, and grain pipeline are local variables that get garbage-collected. Every query through the canonical path since this factory landed has run **zero MTR inference, zero phantom tracking, zero crystallization, zero L2 audit, zero procedural trace logging.**

**Finding F2 — split-brain engines.** The factory builds `CartridgeInferenceEngine` (Phase 3E, learning-capable) AND separate `GrainEngine`/`CartridgeEngine` adapter instances that construct their **own** registries from `cartridges_dir`. Two copies of the cartridge world are loaded. Answers come from the adapters' copy; any learning writes would go to the Phase 3E copy. Even after F1 is fixed, learning and answering would disagree about the state of the world unless the adapters wrap the shared instances.

**Finding F3 — dream bucket absent from canonical path.** The donor threads `dream_bucket_writer` into `CartridgeInferenceEngine` and `GrainRouter`; the factory constructs both without it. No violation logging, no trace substrate, on the canonical path.

## 2. Donor Bugs — DO NOT MIGRATE (fix-on-migration list)

Migrating the donor's *capabilities* is the goal; migrating its *code verbatim* is forbidden. Each bug below, with donor line numbers, and the required behavior:

- **B1. Double query-count increment** (lines ~303 and ~524). `query_count` increments twice per query, so the "every 51 queries" crystallization trigger actually fires on a ~25–26 query cadence and the `if self.query_count > 0` guard at ~467 is always true (dead logic). REQUIRED: exactly one increment per processed query, owned in exactly one place.
- **B2. Double phantom-cycle advance** (lines ~468 and ~493), with mutually contradictory comments ("advance from PREVIOUS query" / "advance after each query"). REQUIRED: `advance_phantom_cycle()` exactly once per query. Confirm intended cadence against `phantom_tracker.py` locking semantics before choosing pre- or post-query; document the choice in the code.
- **B3. AttributeError in trace logging** (line ~560): `context.project` — the dataclass field is `project_context`. Because the block is unguarded, any query with facts and a live dream bucket writer crashes here. Implication: **procedural trace logging has likely never successfully executed on this code path**; existing procedural edges came from elsewhere (probably `phase3e_orchestrator.py`). REQUIRED: correct field; add a regression test that actually executes the trace path.
- **B4. Unbounded, mislabeled trace chains** (lines ~529–562). `recent_facts`/`recent_grains` are appended forever and never cleared, and the **entire accumulated history** is logged as the chain on **every** query, labeled `chain_type="intra_query"`. Chains grow monotonically and the label is false. REQUIRED: per-query chain from this query's facts/grains only; keep a separate bounded deque (suggest maxlen=20) for the co-occurrence/recency features that legitimately want short history. Verify downstream first: check what `sleep_procedural_edge_extractor.py` expects a chain to contain — the fix must match the consumer, not just the label.
- **B5. Inverted confidence** (line ~510): `QueryResult.mtr_confidence = float(error_signal.mean())` reports the raw **error** as confidence (line ~437 computes it correctly as `1.0 − error`). Higher confusion currently reports as higher confidence. REQUIRED: one definition, computed once, used everywhere.
- **B6 (minor). Raw `hat` object serialized into trace context** (line ~559). Enum/object may not be JSON-safe. REQUIRED: serialize `hat.name` or `str(hat)`.

## 3. Target Architecture

The posix cascade stays exactly as it is — it answers queries and it is clean. The donor's machinery becomes a single new component with a narrow contract:

### 3.1 `learning_observer.py` — `LearningObserver`

One class owning everything the donor did *after* answering. Dependency-injected (constructor takes instances, builds nothing itself):

```
LearningObserver(
    mtr_engine,            # KitbashMTREngine (v6.1)
    state_manager,         # MTRStateCheckpoint
    cartridge_engine,      # the SHARED CartridgeInferenceEngine (F2)
    grain_router,          # the SHARED GrainRouter
    mtr_grain_pipeline,    # MTRGrainUnifiedPipeline
    l2_service,            # L2WorkingTheoryService or None
    dream_bucket_writer,   # or None
    crystallization_interval=51,
    device="cpu",
)

observe(query_id, user_query, context, result_summary) -> LearningReport
save_state(session_id) / load_state()
```

`result_summary` is a small dict the orchestrator assembles: `{answered: bool, engine_name, confidence, fact_ids: set, grain_ids: list}`. `LearningReport` is a dataclass: `{mtr_error, mtr_confidence, crystallization: Optional[dict], trace_logged: bool, latency_ms, error: Optional[str]}`.

Inside `observe`, in order: tokenize → kappa from hat (`HatKappaMapper`) → MTR inference (`torch.no_grad()`, update held state) → fact/grain feedback logging (B-fixes applied) → epistemic snapshot → phantom pipeline `process_mtr_query` → single phantom-cycle advance (B2) → grain activation on crystallization → per-query trace logging (B3/B4/B6 fixed) → single counter increment (B1). **Misses are observed too**: exhausted queries (`answered=False`) still run MTR + phantom tracking and log a trace — a miss is Dream Bucket signal, not a skip.

**Resonance stays out.** The posix orchestrator already owns resonance recording/reinforcement and turn sync. The observer never touches `ResonanceWeightService` — one owner per subsystem. (The donor's richer resonance metadata can be ported into the posix call in Step 3 as a one-line enrichment, not an ownership change.)

### 3.2 Orchestrator integration

`QueryOrchestrator.__init__` gains one optional parameter: `learning_observer=None`. In `process_query`, after answer/exhausted determination and metrics, before constructing `QueryResult`:

```
if self.learning_observer:
    try:
        report = self.learning_observer.observe(query_id, user_query, context, result_summary)
    except Exception as e:
        report = None
        self.feed.log_error(query_id, "LEARNING_OBSERVER", str(e))
        logger.error(f"Learning observer failed: {e}")
```

Failure isolation with **loud** telemetry: learning must never break answering, but a dead observer must scream into the diagnostic feed and logs every query — never a bare `pass` (that is how F1 stayed invisible). `QueryResult` gains `learning_report: Optional[dict] = None`. The `shannon`/`_record_phantom_hit` stub is superseded: remove it in Step 3 (the observer's phantom path replaces it; leaving both means double-recording).

### 3.3 Factory after reconciliation

Builds the shared Phase 3E instances once, threads `dream_bucket_writer` into them (F3), constructs adapters **around the shared instances** (F2), constructs the `LearningObserver` from the same instances, and passes it to the orchestrator. Nothing built-and-dropped: after Step 4 every constructed component is reachable from the returned orchestrator.

## 4. Migration Checklist (strict order; each step = one small session; acceptance criteria are executed test output)

**Step 0 — Freeze and baseline.**
Create `attic/` (or confirm existing archive convention). Move `phase3e_orchestrator.py` there with a header note pointing at this spec. Grep the whole tree for imports of `phase3e_orchestrator` and `query_orchestrator` (the donor) — list every importer before moving anything; test/demo scripts that import the donor get updated in Step 5, so only phase3e moves now.
*Acceptance:* `grep -rn "phase3e_orchestrator" --include="*.py"` returns only attic; full test suite (whatever currently passes) still passes.

**Step 1 — Factory coherence (F2, F3).**
Modify `GrainEngine` and `CartridgeEngine` adapters to accept an injected shared engine/router instance (keep the path-based constructor as fallback for standalone use). Factory: construct `CartridgeInferenceEngine` and `GrainRouter` once, WITH `dream_bucket_writer`, and inject them into the adapters. **Ask for `grain_engine.py`, `cartridge_engine.py`, and `interfaces/inference_engine.py` before writing this step** — do not guess adapter internals.
*Acceptance:* new `TEST-factory_coherence.py` asserts object identity — the registry inside the CARTRIDGE adapter **is** the registry inside the learning components (`assert a is b`), and `dream_bucket_writer is not None` on both when a bucket dir is supplied.

**Step 2 — Build `LearningObserver` (§3.1) with all B-fixes.**
Port donor logic block-by-block, applying B1–B6. The observer takes injected dependencies, so unit tests use stub MTR/pipeline objects — no torch required for the contract tests. Include a stub-based regression test per bug: counter increments once; phantom advances once; trace path executes without AttributeError; chain length equals this-query's items; confidence = 1 − error; hat serialized as string. Files: `learning_observer.py` + `TEST-learning_observer.py` (respects two-file rule).
*Acceptance:* `python TEST-learning_observer.py` output pasted, all green, including the six bug-regression tests.

**Step 3 — Wire observer into posix orchestrator (§3.2).**
Surgical diff: constructor param, invocation block, `QueryResult` field, remove `shannon` param + `_record_phantom_hit` (grep for external callers of either first; if any exist outside the factory, ask before removing). Port donor's resonance metadata enrichment into the existing posix resonance call.
*Acceptance:* extend `TEST-orchestrator_contract.py` (Step 6 skeleton can be written first — see §5): observer invoked on answered AND exhausted queries; observer exception → answer still returned AND `feed.log_error` called with `LEARNING_OBSERVER`; no phantom double-recording (stub pipeline records exactly one `process_mtr_query` call per query).

**Step 4 — Factory passes the observer; state lifecycle.**
Factory constructs `LearningObserver` from the shared instances, loads MTR state via `state_manager` at build, passes observer to orchestrator. Add a shutdown/save hook (`orchestrator.close()` → `observer.save_state(session_id)`), and decide+document periodic checkpointing (suggest: every crystallization interval).
*Acceptance:* factory smoke test — build orchestrator, run 3 queries against stub engines, assert `observer.mtr_state['time']` advanced, assert save produces a checkpoint file, rebuild and assert time counter resumes.

**Step 5 — Retire the donor.**
Grep for `from query_orchestrator import` / `import query_orchestrator` across the tree; update each caller to the factory. Move `query_orchestrator.py` to attic with a header pointing here. Fix the posix file's docstring (it still claims to be `kitbash/orchestration/query_orchestrator.py`) and consider renaming `query_orchestrator_posix.py` → `query_orchestrator.py` in a later cosmetic pass — NOT now; one identity change at a time.
*Acceptance:* no non-attic imports of the donor; full suite green; one manual end-to-end query through the factory path with real components, output pasted.

**Step 6 — Contract suite becomes the definition of "orchestrator works."**
`TEST-orchestrator_contract.py` consolidated as the permanent gate (see §5). Add to whatever pre-merge ritual exists. This is the socket contract for the orchestrator boundary; Phase 5 blockers may now proceed, and each blocker's wiring adds its assertions here.

## 5. Contract Test Specification (for `TEST-orchestrator_contract.py`)

Implementing model: the posix orchestrator is fully dependency-injected — test it with hand-rolled fakes (FakeTriage returning a fixed sequence, FakeEngine returning configurable confidence, spy DiagnosticFeed, stub observer). **Ask for `interfaces/triage_agent.py`, `interfaces/inference_engine.py`, and `interfaces/mamba_context_service.py` before writing** — the request/response dataclass fields must match reality, not be guessed. Assertions, minimum set:

1. Cascade honors triage sequence and thresholds; first passing engine wins; ESCALATE sentinel stops the cascade.
2. Exhausted path returns "I don't know" with confidence 0.0 and still invokes the observer.
3. Heartbeat pause/resume bracket the cascade even when an engine raises (finally-path).
4. Turn advances exactly once per query and syncs to resonance/triage.
5. Observer receives correct `fact_ids`/`result_summary`; observer exception does not change the answer and DOES produce `feed.log_error("LEARNING_OBSERVER", ...)`.
6. Exactly one phantom-pipeline call and one cycle-advance per query (spy counts).
7. Factory coherence: shared-instance identity assertions (from Step 1) live here permanently.
8. Trace logging: with a spy dream-bucket writer, one trace per query, chain contains exactly this query's items, `chain_type` truthful, context JSON-serializable.

## 6. Out of Scope (explicitly, so nobody "improves" en route)

No MTR changes beyond swapping the import to `MTR_v6_1` (which is itself gated on its contract suite passing on real hardware first). No triage changes. No Redis wiring (that is Phase 5 blocker #2, which this spec unblocks). No renaming sweep beyond the docstring fix. No new features inside the observer that the donor didn't have. If a step reveals something not covered here, stop and ask — do not extend the spec unilaterally.

---
*Written against read-only copies dated 2026-07-07 (donor 789 lines, posix 473 lines, factory 322 lines). If files have drifted since, re-verify §1–§2 line references before executing.*
