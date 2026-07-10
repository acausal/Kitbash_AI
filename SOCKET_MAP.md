# KITBASH SOCKET MAP

**Date:** 2026-07-07 (initial pass, from Fable audit of read-only copies)
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
| Query entry (factory → orchestrator) | `create_query_orchestrator()` → `process_query(str, ctx) -> QueryResult` | **RED** | F1: factory builds MTR/state/pipeline and never passes them; F2: duplicate engine registries. SPEC_ORCHESTRATOR_RECONCILIATION governs. Green = Steps 0–6 complete + contract suite. |
| TriageAgent | `interfaces/triage_agent.py`: `decide(TriageRequest) -> TriageDecision` | YELLOW | Interface-driven, swappable (rule-based today, learned later — Phase 5+). Interfaces package **unverified**: not in audit scope; implementing models must request it. |
| InferenceEngine: GRAIN | `interfaces/inference_engine.py`: `infer(InferenceRequest) -> InferenceResponse` | YELLOW | Cascade slot. Adapter builds own registry (F2, fixed in Step 1 of spec). |
| InferenceEngine: CARTRIDGE | same | YELLOW | Same F2 caveat. |
| InferenceEngine: BITNET | same (HTTP to local server) | PLANNED | Factory slot exists behind `enable_bitnet`; server not deployed. |
| InferenceEngine: LLM / specialists | same | PLANNED | Phase 4+ cascade tail. The "LLM as generation peripheral" socket. |
| MambaContextService | `get_context(MambaContextRequest)` | YELLOW | Mock only (`mock_mamba_service.py`). Real temporal-window service is a future swap; socket shape already honored by orchestrator. |
| DiagnosticFeed | `log_query_*`, `log_layer_*`, `log_error`, `log_metric` | YELLOW | No-op stand-in when Redis absent (acceptable soft-fail: telemetry, not contract data). Real feed = bus attachment (§4). |

## 2. Learning Plane (the observing path)

| Socket | Interface | Status | Evidence / Notes |
|---|---|---|---|
| LearningObserver | `observe(query_id, query, ctx, result_summary) -> LearningReport` | PLANNED→ | Defined in reconciliation spec §3.1; Step 2 builds it, Step 3 wires it. The single socket for all post-answer learning. |
| MTR engine | `KitbashMTREngine.forward(tokens, state, target_layer, kappa)` + `get_epistemic_snapshot` | YELLOW (green-pending) | v6.1 written with `TEST-MTR_v6_1_contract.py`; **suite not yet executed on real hardware** — flips green when the run output exists. v6 in place = RED; do not deploy v6. |
| Epistemic layer names | `MTR_v6_1.LAYER_NAMES` (single source of truth) | YELLOW | Consumers (`mtr_grain_bridge` weights dict) still on stale names until the one-line diff lands + contract test. |
| GrainRouter.search_grains | `(concepts, recent) -> [(grain_id, score)]` | **RED (measured)** | Harness run 2026-07-07: MRR 0.131 ≈ random on query-conditioned task; `query_concepts` unused in scoring. Fix path: make score consult concepts, re-run harness, paste delta. If intent is "coarse filter only," rename/document the contract instead — either resolution flips this yellow. |
| MTR↔Grain bridge | `MTRGrainUnifiedPipeline.process_mtr_query(...)` | RED | Soft-fail patterns (`dict.get` on layer names, bare `except: pass` in concept extraction); salience>0.3 gate calibrated to sigmoid regime. Fail-loud sweep target. |
| HatKappaMapper | `get_kappa(hat) -> float` | YELLOW | The L4→routing rigidity channel. Severed in v6, restored in v6.1; needs one contract assertion (kappa reaches MTR — in orchestrator contract suite Step 3). |
| Phantom tracker / crystallization | `advance_phantom_cycle`, crystallize-at-interval | RED | Donor bugs B1/B2 (double increment, double advance) mean the 51-query cadence has never been the real cadence. Fixed inside LearningObserver (Step 2). |
| Resonance weights | `record_pattern / reinforce_pattern / advance_turn` | YELLOW | Single-owner rule: orchestrator owns it; observer must not touch (spec §3.1). |
| MTR state manager | `MTRStateCheckpoint.save/load/exists` | YELLOW | Loaded-then-dropped in factory today (F1). Lifecycle defined in spec Step 4. |
| L2 Working Theory service | `L2WorkingTheoryService` (read-only audit) | PLANNED→ | Initialized in donor only; canonical wiring lands with observer. Full service = Phase 5 blocker #3 (Mutation 2). |

## 3. Sleep Plane (the consolidating path)

| Socket | Interface | Status | Evidence / Notes |
|---|---|---|---|
| Dream Bucket write | `DreamBucketWriter` + `log_false_positive / log_consistency_violation / log_hypothesis / log_trace` | YELLOW | Append-only JSONL, clean function contracts. But: canonical path never wrote to it (F1/F3), and donor trace path had B3 (AttributeError) + B4 (unbounded mislabeled chains) — so **verify existing trace records' provenance and shape before Stage 1.5 trusts them.** |
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
| MTR contract suite | `TEST-MTR_v6_1_contract.py` | YELLOW | Written, compile-checked, statically verified; awaiting first execution on hardware with torch. |
| Orchestrator contract suite | spec §5 | PLANNED | Deliverable of reconciliation Steps 3–6. |

---

## Phase 5 Critical Path (the cells that define "yak shaved")

In dependency order: **Query entry (RED→) → LearningObserver (build+wire) → MTR v6.1 (execute suite) → stream format spec (RED→) → RedisBlackboard wiring → grain registry format contract → Mutation 1 → L2 service (Mutation 2).** When every cell on this line is GREEN, refactoring is over and building resumes. Everything else on this map is backlog by definition — including things that are genuinely broken. That is the license to stop looking.

## Maintenance Rules

1. This document changes in the same commit/session as any socket it describes. A socket change without a map change is a spec violation.
2. Initial statuses above are from a single Fable audit pass of read-only copies; anything marked *unverified* gets verified the first time a task touches it, not preemptively.
3. Re-audit cadence: after each Phase-blocker completes, one pass to catch drift. Otherwise the map is event-driven, not scheduled — a scheduled full re-audit is the yak-shave spiral wearing a badge.
