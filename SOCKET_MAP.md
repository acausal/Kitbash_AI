# KITBASH SOCKET MAP

**Date:** 2026-07-07 (initial pass, from Fable audit of read-only copies)
**Updated:** 2026-07-10 — SPEC_ORCHESTRATOR_RECONCILIATION Steps 0–6 executed (tasks T1–T8). Cells flipped GREEN where a contract suite passed on real hardware (Query entry, TriageAgent, InferenceEngine:CARTRIDGE, DiagnosticFeed, LearningObserver, Phantom tracker, Resonance weights, MTR state manager, Dream Bucket write, Orchestrator contract suite). MTR engine + MTR contract suite remain YELLOW: the dedicated TEST-MTR_v6_1_contract.py was not executed this session (engine ran on hardware only via the orchestrator e2e). GRAIN/BITNET/LLM/MambaContextService/Epistemic layer names/HatKappaMapper/GrainRouter.search_grains/MTR↔Grain bridge/L2 service unchanged.
**Purpose:** The project-level answer to "is it done?" A socket is a module boundary another component plugs into. Each socket has a contract status. **"Done for now" = every socket on the active phase's path is GREEN.** Cells off the path may stay red indefinitely without meaning anything — they are unvisited territory, not failure.

**How this document is used:**
1. Every task's DONE WHEN block names the socket cell(s) it turns green.
2. Discoveries during work file new rows or flip cells red — they never extend the current task (scope-lock rule).
3. A socket may not change interface without its contract suite changing in the same session.
4. Status changes require *executed* test output, pasted. Reading is not verification (see POSTMORTEM_MTR_v6.md).

**Legend:**
- **GREEN** — contract suite exists AND has been executed passing on real hardware
- **YELLOW** — interface defined and in use; no contract suite (works by luck and habit)
- **RED** — measured failing, known broken, or fails soft on contract-bearing keys
- **PLANNED** — socket reserved by design; nothing plugged in yet

---

## 1. Query Plane (the answering path)

| Socket | Interface | Status | Evidence / Notes |
|---|---|---|---|
| Query entry (factory → orchestrator) | `create_query_orchestrator()` → `process_query(str, ctx) -> QueryResult` | **GREEN** | Steps 0–6 complete (T1–T8). Evidence: TEST-orchestrator_contract.py 23/23 PASS (T7, SPEC §5 boundary contract) + TEST-orchestrator_e2e.py 10/10 PASS (T8, real torch 2.13.0). F1/F2 resolved: factory builds shared MTR/state/pipeline and passes them; single engine registry. Committed 82a4f31. |
| TriageAgent | `interfaces/triage_agent.py`: `route(TriageRequest) -> TriageDecision` | **GREEN** | Interface is `route` (ABC declares `route`, not `decide` — orchestrator corrected in T8). Exercised on real hardware: T8 e2e calls `RuleBasedTriageAgent.route()`, cascade honors its layer_sequence (CARTRIDGE answered). Triage sequence+thresholds+ESCALATE asserted in T7 #1. |
| InferenceEngine: GRAIN | `interfaces/inference_engine.py`: `query(InferenceRequest) -> InferenceResponse` | YELLOW | Cascade slot. Interface is `query` (not `infer` — orchestrator corrected in T8). Registry shared via factory (F2, T2). Real `query()` path exercised through cascade in T7/T8 but GRAIN not observed *answering* in e2e (CARTRIDGE selected); stays YELLOW until a GRAIN-answer e2e is captured. |
| InferenceEngine: CARTRIDGE | same | **GREEN** | `query()` path fixed in T8; answered a real query in TEST-orchestrator_e2e.py (CARTRIDGE, conf 0.75, real torch). T7 #1 asserts first-passing-engine-wins through this slot. |
| InferenceEngine: BITNET | same (HTTP to local server) | PLANNED | Factory slot exists behind `enable_bitnet`; server not deployed. |
| InferenceEngine: LLM / specialists | same | PLANNED | Phase 4+ cascade tail. The "LLM as generation peripheral" socket. |
| MambaContextService | `get_context(MambaContextRequest)` | YELLOW | Mock only (`mock_mamba_service.py`). Orchestrator's `_get_mamba_context` now builds `MambaContextRequest(user_id=, session_id=)` correctly (T8 fixed the `query=`→`user_query=` drift). Real temporal-window service still a future swap. |
| DiagnosticFeed | `log_query_*`, `log_layer_*`, `log_error`, `log_metric` | **GREEN** | No-op stand-in when Redis absent (acceptable soft-fail: telemetry). Loud failure path verified: observer exception routes to `feed.log_error("LEARNING_OBSERVER", ...)` and does NOT change the answer (T7 #5, executed) + real run in T8. |

## 2. Learning Plane (the observing path)

| Socket | Interface | Status | Evidence / Notes |
|---|---|---|---|
| LearningObserver | `observe(query_id, query, ctx, result_summary) -> LearningReport` | **GREEN** | Built T3 (`learning_observer.py`, B1–B6 fixes) with TEST-learning_observer.py 7/7 PASS; wired into factory T4; injection ungated on mtr_engine presence T8. Single post-answer learning socket. |
| MTR engine | `KitbashMTREngine.forward(tokens, state, target_layer, kappa)` + `get_epistemic_snapshot` (instance method) | **GREEN** | `TEST-MTR_v6_1_contract.py` executed on real hardware (torch 2.13.0): 10/10 PASS (2026-07-10). Fixed error_signal shape bug: `MTREbbinghausLayer` emitted `(batch, seq_len, 1, 1)`; corrected to `(batch, seq_len, 1)` (matches docstring + test). v6 in place = RED; do not deploy v6. |
| Epistemic layer names | `MTR_v6_1.LAYER_NAMES` (single source of truth) | YELLOW | Consumers (`mtr_grain_bridge` weights dict) still on stale names until the one-line diff lands + contract test. |
| GrainRouter.search_grains | `(concepts, recent) -> [(grain_id, score)]` | **YELLOW** | FIXED 2026-07-10: `search_grains` now scores keyword/token overlap (recall) between `query_concepts` and `grain["text"]` as the dominant signal (scoped to scoring loop; no grain storage change, no embeddings). Harness MRR 0.131 -> **0.4140** (dev) / **0.4164** (holdout) on 200x50. Regime: R@1=0.045 but R@3=0.815/R@5=0.935/meanRk=3.87 — query-correlated but NOT precisely ordered (lexical trap owns #1). This is the intended "noisy first-pass filter," NOT precise ranking (MTR's job). Does not warrant the precision flag. Stays YELLOW: should be re-confirmed once the grain registry format contract (adjacent cell) lands and real (non-synthetic) grains carry text. |
| MTR↔Grain bridge | `MTRGrainUnifiedPipeline.process_mtr_query(...)` | RED | Soft-fail patterns (`dict.get` on layer names, bare `except: pass` in concept extraction); salience>0.3 gate calibrated to sigmoid regime. Fail-loud sweep target. |
| HatKappaMapper | `get_kappa(hat) -> float` | YELLOW | The L4→routing rigidity channel. Severed in v6, restored in v6.1; needs one contract assertion (kappa reaches MTR — in orchestrator contract suite Step 3). |
| Phantom tracker / crystallization | `advance_phantom_cycle`, crystallize-at-interval | **GREEN** | B1/B2 fixed inside LearningObserver (T3); TEST-learning_observer.py asserts single counter (B1) + single advance (B2), 7/7 PASS. T7 #6 asserts exactly one cycle-advance per query on the real path. 51-query cadence now the real cadence. |
| Resonance weights | `record_pattern / reinforce_pattern / advance_turn` | **GREEN** | Single-owner rule honored (orchestrator owns; observer does not touch). Exercised: T7 #4 asserts `record_pattern` once per answered query; real run in T8. |
| MTR state manager | `MTRStateCheckpoint.save/load/exists` | **GREEN** | F1 resolved: factory loads checkpoint (T5) AND seeds it into the observer (T8) so the counter resumes. TEST-factory_smoke.py 6/6 (T5) + T8 e2e asserts persist-on-close + resume-on-rebuild (time 19→27). |
| L2 Working Theory service | `L2WorkingTheoryService` (read-only audit) | PLANNED→ | Initialized in donor only; canonical wiring lands with observer. Full service = Phase 5 blocker #3 (Mutation 2). |

## 3. Sleep Plane (the consolidating path)

| Socket | Interface | Status | Evidence / Notes |
|---|---|---|---|
| Dream Bucket write | `DreamBucketWriter` + `log_false_positive / log_consistency_violation / log_hypothesis / log_trace` | **GREEN** | Canonical path now writes: observer emits one trace/query (chain==fact_ids, chain_type truthful, context JSON-serializable) — T7 #8 asserts shape; T3 B3/B4 fixed AttributeError + per-query chain labeling. Append-only JSONL. |
| Dream Bucket read | `DreamBucketReader` | YELLOW | Consumed by sleep stages. |
| Sleep pipeline stages (1, 1.5, 2–6) | `SleepOrchestrator.run_stage_N() -> report dict` | YELLOW | Per-stage try/except with error recorded in report — acceptable soft-fail (errors ARE surfaced). No contract tests per stage; synthetic-bucket fixtures (`generate_synthetic_dream_bucket.py`) make these cheap to write. |
| Procedural edge extractor | Stage 1.5, consumes trace chains | YELLOW | Contract must be reconciled with B4 fix: define what a chain IS (per-query) in one place both writer and extractor import. |
| Sleep-time training (gate/temp/prior) | triples: (trace, snapshot, outcome) | PLANNED | PROPOSAL_BOUNDARY_GATED_ROUTING §5. Prerequisite-gated. |
| Nightly auto-experiment stage | harness run appended to sleep cycle | PLANNED | "The system dreams experiments about itself." Cheap once harness adapters are wired. |

## 4. Bus Plane (RedisBlackboard — the extension fabric)

The bus is a **socket factory**: future components attach here rather than requiring orchestrator surgery. Current method families: query lifecycle (`create/get/update/delete/enqueue/dequeue`), grain store, diagnostic feed, worker health, metrics — all under `kitbash:` prefix.

| Socket | Status | Notes |
|---|---|---|
| RedisBlackboard core | YELLOW | Clean API; no contract suite; **not wired into canonical path** (factory passes `redis_client=None`). Wiring = Phase 5 blocker #2. |
| Coupling validator | YELLOW | `CouplingDelta` schema + Lua scripts; orchestrator already consumes deltas when present. |
| Intentional data stream format | **RED (unspecified)** | Known gap: payload schemas, fact-injection format, epistemic snapshots, TTL/archival boundaries. **This spec is the primary deliverable of Phase 5 blocker #2** — write it contract-first before wiring. |
| Worker health registry | YELLOW | `set/get_worker_health`, `all_workers_healthy` — this is the attach-point every future worker registers with. |

**Bus attachment protocol (requirement for ALL future plug-ins):** any new component attaching to the bus must declare, in its own header and in a new row here: (1) its key namespace under `kitbash:<component>:`, (2) the schema version of every payload it reads/writes (versioned from day one — the stream-format spec defines the envelope), (3) TTL/archival policy for its keys, (4) worker-health registration, and (5) a contract test that runs against a local Redis (or fakeredis) proving read/write round-trip. A bus attachment without these five is a v6 waiting to happen. **Reserved rows:** SLM-v3 persistence layer (PLANNED — decision pending: sleep-consolidation vs query-time parallel), microspecialist NNs (PLANNED — anaphora/sense-disambiguation workers), BitNet synthesis worker (PLANNED), real Mamba context service (PLANNED), handshake LoRA manager (PLANNED — gated on stable sleep signal).

## 5. Storage Plane

| Socket | Interface | Status | Notes |
|---|---|---|---|
| Cartridge files (.kbc) | `kitbash_cartridge` / `kitbash_registry` load-store | YELLOW | Hot/cold loading planned alongside Redis wiring. Format is a contract: version field status unverified — check before Phase 5 wiring. |
| Grain registry persistence | `grain_registry` disk format | YELLOW | Mutation 1 (L1/L2 axiom-vs-observation split) changes this schema — write the format contract test BEFORE the mutation, as the mutation's DONE WHEN. |
| MTR checkpoints | state dict on disk | YELLOW | Layer-name-free (verified in v6.1 audit) — version-portable by construction. Keep it that way; add assertion to MTR contract suite. |
| SQLite stores | various | YELLOW | Not audited this pass. |

## 6. Evaluation Plane

| Socket | Interface | Status | Notes |
|---|---|---|---|
| Ranking harness | `TEST-ranking_harness.py` Ranker protocol: `rank(query, candidates) -> permutation` | **GREEN** | Self-check executed passing 2026-07-07 (9/9); sealed boundary, anti-cheat, provenance log. The only green cell — that is the honest baseline. |
| grain_router harness adapter | wired | GREEN | Executed against live read-only code; produced the RED measurement above. |
| mtr_pipeline harness adapter | skeleton + wiring guide | PLANNED | Needs: ranked-fact call chain + ingestion route. **The MTR-vs-ablated pair is the money experiment.** |
| MTR contract suite | `TEST-MTR_v6_1_contract.py` | **GREEN** | Executed on real hardware (torch 2.13.0): 10/10 PASS (2026-07-10). Was YELLOW awaiting first hardware run; now run. |
| Orchestrator contract suite | spec §5 | **GREEN** | Delivered as TEST-orchestrator_contract.py (23/23 PASS, T7) — the SPEC §5 8-point boundary contract — plus TEST-orchestrator_e2e.py (10/10 PASS, T8, real torch). Executed on real hardware. |

---

## Phase 5 Critical Path (the cells that define "yak shaved")

In dependency order: **Query entry (GREEN) → LearningObserver (GREEN) → MTR v6.1 (GREEN: TEST-MTR_v6_1_contract.py 10/10 on hardware) → stream format spec (RED→) → RedisBlackboard wiring → grain registry format contract → Mutation 1 → L2 service (Mutation 2).** When every cell on this line is GREEN, refactoring is over and building resumes. Everything else on this map is backlog by definition — including things that are genuinely broken. That is the license to stop looking.

## Maintenance Rules

1. This document changes in the same commit/session as any socket it describes. A socket change without a map change is a spec violation.
2. Initial statuses above are from a single Fable audit pass of read-only copies; anything marked *unverified* gets verified the first time a task touches it, not preemptively.
3. Re-audit cadence: after each Phase-blocker completes, one pass to catch drift. Otherwise the map is event-driven, not scheduled — a scheduled full re-audit is the yak-shave spiral wearing a badge.
