# Kitbash

A local-first personal cognitive architecture built around a small language model, designed for continuous learning without catastrophic forgetting.

This is a personal, long-running project, not a commercial product or a business tool. It is built primarily through LLM-assisted development by someone without a professional software background, and it is under active, sometimes messy, construction. The status section below is honest about what currently works and what doesn't.

## What this is

Kitbash treats the language model as a swappable generation component rather than as the seat of orchestration, memory, or routing. State tracking, long-term memory, contextual routing, and identity continuity are handled by deterministic, symbolic code around the model, not by the model itself. The design bet is that a disciplined, mostly symbolic memory and routing layer, paired with a small local model, can behave more consistently over time than a larger model operating without persistent structure around it.

Everything runs locally by default. There are no required cloud services and no subscription dependency. An external, stronger model can optionally be called for specific high-value analytical work (code review, architecture audits), but this is gated behind explicit consent and is not part of the runtime loop.

## How this differs from typical agent frameworks

Most agent frameworks put the LLM in charge: it plans, calls tools, decides what to remember, and often decides how to route its own reasoning. Kitbash inverts that relationship in a few specific ways.

**The model does not orchestrate itself.** Routing, memory writes, and layer selection are handled by separate, testable code. The model is called to generate text once the surrounding system has already decided what context it should see and why. This is a deliberate rejection of the assumption that scaling capability means scaling context windows, parameter counts, or how much responsibility gets handed to the model itself.

**Learning is pushed to the cheapest layer that can hold it.** New information first tries to live in coarse structural relationships between stored knowledge units ("cartridges"). If a pattern proves stable, it gets crystallized during an offline consolidation pass. Only patterns that survive that process become candidates for small, targeted fine-tuning. Full retraining of the base model is treated as a near-last resort, not a routine operation. Most frameworks either skip persistent learning entirely (the model just gets a longer prompt) or default to fine-tuning as the first lever pulled.

**Retrieval is deliberately two-stage and deliberately imprecise at the first stage.** A cheap, high-recall filter (allowing false positives on purpose) narrows a large knowledge base down to a candidate set. A separate, more expensive ranking stage than picks from that candidate set, or escalates to a full scan if it isn't confident. The false positives from the first stage are treated as useful signal about the shape of the knowledge base, not as noise to eliminate.

**Knowledge mutation is separated from query execution in time, not just in code.** The knowledge structures are effectively read-only while a query is being answered. Learning, reweighting, and structural changes happen during a separate offline consolidation phase, modeled loosely on sleep-stage memory consolidation. This avoids a class of bugs common to frameworks that mutate shared state mid-conversation, and it makes the live query path easier to reason about and to keep fast.

**Verification is structural, not narrative.** Components are tracked against a contract map showing which interfaces have an executed, passing test suite versus which are merely wired up and working by habit. A module is not considered done because it reads correctly or because a description of it sounds right; it is considered done when there is executed output proving the contract holds. This same standard is applied to the project owner's own judgment, not only to model output.

**Anomalies are treated as information about the system, not just as errors to suppress.** When the system's internal predictions don't match outcomes, that mismatch is logged and used during consolidation to recalibrate confidence, rather than discarded or immediately corrected in-context.

## Architecture, briefly

- A six-layer knowledge stack, from hardwired facts and crystallized long-term knowledge at the bottom, up through working theory, immediate context, behavioral mode, and session-level state at the top. Lower layers change rarely; upper layers change per query or per session.
- Knowledge units ("cartridges") indexed by topic, with hot/cold storage tiering.
- A noisy, high-recall filtering layer ("grains") followed by a separate ranking and salience engine.
- An append-only episodic log that overflow and working memory get written to during live use.
- An offline, multi-stage consolidation pipeline that reads that log, extracts patterns, generates and tests hypotheses, and folds validated results back into the knowledge stack.
- A shared-state coordination layer (Redis-backed) intended to let multiple components observe consistent system state without direct calls between them.

## Status

Last updated: 2026-07-15. This is not a finished system — active development, not a stable release. Component status is tracked on `SOCKET_MAP.md` (per-interface contract map: GREEN = executed passing test suite, YELLOW/RED = wired but not fully verified). What follows is the honest high-level picture.

**Current milestone:** a working chat front-end exists — `kitbash_cli.py` (stdio JSON) and `kitbash_web.py` (browser POC) — driven by the orchestrator with CARTRIDGE + BITNET + live BitMamba context. Both models are visibly engaged in the web UI. This is a proof-of-concept surface, not the final product.

**Query / cascade plane — GREEN and externally reachable.**
The chat path runs end to end and is verified:
- Routing/triage, CARTRIDGE (crystallized knowledge), BITNET (BitNet ternary-net, now the primary learned-inference net — threshold tuned to 0.65, ordered before CARTRIDGE so it competes in normal traffic), and MambaContextService (RealMambaService, Option B2 over a persistent `bitmamba_server` shim) are all wired and tested.
- Both models run standalone and are integrated into the orchestrator; BITNET is now evaluated first in normal traffic (threshold 0.65, ordered ahead of CARTRIDGE) and wins when confident, CARTRIDGE answers when BITNET doesn't clear its bar, and BitMamba context is **consumed live** — `context_1hour` is prepended to the engine prompt (`[Recent context]` block). The web POC shows which engine answered and a "BitMamba context injected" badge, so both models are visibly engaged.
- GrainRouter.search_grains, LearningObserver, MTR engine + contract suite, Phantom/crystallization, Resonance, and L2 working-theory service are GREEN.

**Prerequisite — start the BitNet server:** the cascade's BITNET tier talks to a local
`llama-server.exe` (llama.cpp) on `127.0.0.1:8080`. Launch it with the bundled script, which
encodes the stable config (`-c 4096` context; CPU-only build, so `-ngl` is a no-op and BitNet
uses ~0 VRAM):
```bash
bash scripts/start_bitnet.sh          # foreground; background it or run via a process manager
```
⚠️ **Machine-specific paths:** `scripts/start_bitnet.sh` currently hard-codes the maintainer's
`B:\ai\llm\kitbash\...` layout for the binary and model. Override per-machine via env vars
(no edit needed):
```bash
BITNET_BIN=/path/to/llama-server.exe \
BITNET_MODEL=/path/to/model.gguf \
BITNET_CTX=4096 bash scripts/start_bitnet.sh
```
(BitNet is optional — the CLI/web run without it via `KITBASH_ENABLE_BITNET`, falling back to
CARTRIDGE.)

**Two ways to drive it (both verified this session):**
- `kitbash_cli.py` — stdio JSON bridge. stdin = `{"query":...}`, **stdout = chat-only JSON** (`answer_chunk` / `answer_done` / `error`), **stderr = internal ops/logs**. Env toggles: `KITBASH_ENABLE_BITNET`, `KITBASH_ENABLE_MAMBA`, `KITBASH_BITNET_URL`. Wire contract in `docs/done/CLI_PROTOCOL.md`.
- `kitbash_web.py` — dead-simple POC web UI (stdlib `http.server`, no deps). `GET /` serves a chat page, `POST /query` streams the CLI's chat output to the browser, `GET /ops` exposes the internal operational stream. Run `python kitbash_web.py` → http://127.0.0.1:8777.

**Not yet done (separate workstreams, not blockers for chat):**
- Sleep pipeline stages (consolidation, hypothesis generation, recalibration), MTR↔Grain bridge (RED — soft-fail patterns), Epistemic layer names (YELLOW), HatKappaMapper, Dream Bucket read, RedisBlackboard core (API built, not wired into canonical path), Coupling validator, Cartridge file format, MTR checkpoints, SQLite stores. These are the memory/consolidation and shared-state planes — intentionally out of scope for the current chat-POC milestone.
- **Success Signal Integration (Dream Bucket ↔ Orchestrator):** spec `docs/SPEC-SUCCESS_SIGNAL_INTEGRATION_v1.md`, deviation audit `docs/DEVNOTE-SUCCESS_SIGNAL_INTEGRATION.md`, impl log `docs/STATUS_2026-07-15_success_signal.md`. **As of 2026-07-15:** ALL STEPS DONE & verified (commits `d4a6938`, `0e8057b`, `c55d0db`, `7cc1a37`) — `dream_bucket.py` gained `success_traces` logging, `query_completion_heuristic.py` provides `CoherenceChecker`, and `query_orchestrator_posix.py` wires the coherence check post-answer. The spec's fixed `min_response_length=100` was replaced by a query-aware dynamic threshold (factual/explanation/other bases; confidence-scaled). `slm success-stats` CLI deferred to post-Phase-A.
- **WebUI & Execution Trace Visibility:** spec `docs/SPEC-WEBUI_AND_TRACE_VISIBILITY_v1.md`, deviation audit `docs/DEVNOTE-WEBUI_AND_TRACE_VISIBILITY.md`, plan `docs/PLAN-WEBUI_TRACE_VISIBILITY.md`. **As of 2026-07-15:** feasible slice DONE & verified (commits `a12587d`, `fb77562`, `9fa41ce`) — `execution_tracer.py` (pure TraceEvent/ExecutionTracer), `kitbash_cli.py` emits `trace_event` NDJSON (query_entry/mamba_context/engine_cascade/final_assembly from `QueryResult`), and `static/index.html` gained in-session chat history + a collapsible debug-trace pane. Audit found the spec assumed a nonexistent Flask/FastAPI server-side tracer; the real trace point is the CLI subprocess (see DEVNOTE). Server-side tracer, `context_builder` point (needs `QueryResult` extension), and `/trace` persistence deferred.
- **MTR v6.1 Profiling + Contract Checks:** `mtr_profiler.py` (core, repo root). **As of 2026-07-15:** DONE (commit `cde7d14`). Measures real latency of the production MTR-Ebbinghaus engine (config `vocab_size=50257, d_model=256, d_state=144`) + asserts 5 explicit contracts. Behavioral contract suite `tests/TEST-MTR_v6_1_contract.py` also RAN: **10/10 PASS** (under `.venv`, torch 2.13+cpu). Measured: init ~190ms, `forward()` p50 ~23ms (p95 ~27ms), `get_epistemic_snapshot()` p50 ~19ms. Caveats: (a) must run under `.venv` — bare `python` has no torch, so the profiler reports a clean blocker (exit 2), never fakes green; (b) `tools/run_TEST.py` does NOT cover `/tests/*.py` or `mtr_profiler.py` — run them directly; (c) latency bounds in `mtr_profiler.py` are explicit placeholders, tighten from evidence.
- **L5 Observation Logger (roadmap Phase D2, observation-only):** `l5_observation_logger.py` + orchestrator wiring. **As of 2026-07-15:** DONE (commit `7f7bbe7`). Non-acting `L5ObservationLogger.observe()` records per-query signals the live orchestrator exposes (query, winning engine, confidence, latency, triage layer_sequence, turn, timestamp) + any `hat`/`topic`/`session_id` passed via `context` (forward-compatible, `None` when absent — never fabricated). `summarize()` reports distributions over the persisted JSONL. Wired into `query_orchestrator_posix.process_query` (guarded, never blocks answering). Caveat: logger unit-tested standalone; the orchestrator *wiring* is `py_compile`-clean but NOT executed end-to-end (needs engines running). The live orchestrator does not compute hat/topic itself (those only existed in retired `attic/query_orchestrator.py`; Mamba/L4-L5 is off here).
- **Error Categorization (microspecialist selection):** `error_categorizer.py` (core, repo root). **As of 2026-07-15:** DONE (commit `120371d`), but REDESIGNED on the REAL violation schema. The spec `docs/PIPELINE-ERROR_CATEGORIZATION_FOR_SPECIALISTS.md` assumed a `user_complaint`/`context_at_failure`/`grain_confidence` field and tools (`log_parser`, `conditional_pattern_detector`, `pattern_explainer`, `text_search.match_any`) that DO NOT exist. Real record (`dream_bucket.log_consistency_violation`) carries `dissonance_type`/`returned_confidence`/`mtr_error_signal`/etc. — no complaint text. The categorizer classifies on those real fields; the spec's 8 natural-language categories (coreference, sense ambiguity, ...) are intentionally NOT fabricated (report states this). Reads via real `DreamBucketReader.read_live_log('violations')`. Verified END-TO-END on REAL synthetic violations (`generate_synthetic_dream_bucket` → categorizer): all records categorized, report produced. Caveat: real-data run pending real query violations.

**Tests** live in `tests/` (run `python tests/TEST-<name>.py` from the repo root). **Specs/docs** live in `docs/done/` (project specs, archived from `docs/`); tool specs live in `tools/`. Web UI assets live in `static/`. The per-day work log lives in `status/`. `SOCKET_MAP.md` remains at the repo root; historical `STATUS_2026-07-10.md` is archived under `docs/done/`.

## Tools (`tools/`)

`tools/` is an isolation-first sandbox (see `tools/README.md` for the full catalog and the Isolation Contract). Two self-contained batches of stateless, deterministic, **stdlib-only** tools were built there against the Historical AI shared contract:

- **Batch 1 (2026-07-14):** six retrieval / IR / stats tools — `frequency_analysis`, `inverted_index_builder`, `boolean_search`, `tfidf_ranker`, `markov_chain`, `naive_bayes_classifier`.
- **Batch 2 (2026-07-15):** three graph / deduplication tools — `duplicate_detection`, `hypergraph_traversal`, `topological_statistics`.

All nine share `tools/historical_common.py` (config/envelope/CLI boilerplate) and are covered by a durable runner, `tools/run_TEST.py` → **92 PASS / 0 FAIL**. Registry/sieve_hooks integration is deferred to post-1.0. Both batches are confined to `tools/`; they do not touch the core pipeline or `SOCKET_MAP.md`.

## Influences

Cyc, Complementary Learning Systems theory, ACT-R and SOAR style cognitive architectures, blackboard architectures (Hearsay-II lineage), and Lakoff and Johnson's work on image schemas.

## License

(add license here)
