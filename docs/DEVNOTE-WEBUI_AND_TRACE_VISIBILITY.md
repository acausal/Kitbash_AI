# DEVNOTE: SPEC-WEBUI_AND_TRACE_VISIBILITY_v1 — Audit

**Spec:** `docs/SPEC-WEBUI_AND_TRACE_VISIBILITY_v1.md` (Status: Ready for Design + Implementation)
**Auditor:** Hermes (verified against repo at HEAD, not inferred)
**Date:** 2026-07-15
**Scope classification:** Core infrastructure + frontend (NOT `tools/` sandbox)

## Verdict
The UI/UX goals (session chat history + execution-trace visibility) are sound and
wanted. But the spec is written against a **nonexistent serving architecture**: it
assumes an in-process Flask/FastAPI server with a `query_orchestrator.py` you can
decorate with a server-side `ExecutionTracer`, a `context_builder.build()` function,
and module-level `cartridge_loader.retrieve()` / `mtr.rank()` / `bitnet.generate()`
calls. **None of that matches the real system.** This is the same stale-layout
pattern as SPEC-SUCCESS_SIGNAL_INTEGRATION_v1 and DESIGN-DOCUMENT_CHUNK_RETRIEVAL_v1,
but more severe: it invents a whole web tier that isn't there.

The real POC UI + server **already exist and work**. The spec reimagines them from
scratch. Treat it as a *product/UX brief*, not an implementation plan.

## What actually exists (source-verified)
| Real component | Path | Reality |
|---|---|---|
| Web server | `kitbash_web.py` | `http.server` `BaseHTTPRequestHandler` (stdlib). **NOT** Flask/FastAPI. |
| Serving model | `kitbash_web.py` `do_POST` | `POST /query` **spawns `kitbash_cli.py` as a subprocess**, buffers its stdout, returns one NDJSON body. No streaming generator, no `/trace` endpoint, no in-process orchestrator. |
| CLI event format | `kitbash_cli.py` | NDJSON lines on stdout: `answer_chunk`, `answer_done` (`query_id`, `engine`, `confidence`, `total_latency_ms`, `mamba_injected`), `error`. The CLI is the natural trace-collection point (it holds the `QueryResult` + timing). |
| Frontend | `static/index.html` | **Exists** (spec claims to design it from scratch). Has `#q`, `#send`, `#opsbtn` (Toggle OPS), `#answer`, `#meta`, `#ops`; parses the NDJSON above. |
| Orchestrator | `query_orchestrator_posix.py` | Real class `QueryOrchestrator`; `process_query()` returns `QueryResult` (with `layer_results: List[LayerAttempt]`, `mamba_injected`, `engine_name`, `confidence`, `query_id`, `answer`). Uses `self.engines[layer].query(request)`, `self.mamba_service.get_context(...)`. **No `finalize_query`, no `cartridge_loader.retrieve`, no `mtr.rank`, no `bitnet.generate`, no `context_builder`.** |
| Cartridge API | `cartridge_loader.py` | `CartridgeInferenceEngine.query(request, limit=5)` → `CartridgeInferenceResponse`. **No `retrieve()`.** |
| `execution_tracer.py` | (none) | Genuinely new; the dataclass module is buildable standalone (no repo deps). |

## Deviations (spec assumption -> reality)
1. **Server framework:** spec's `@app.post("/query")` async generator ⇒ reality is stdlib
   `http.server`, subprocess-per-request, buffered NDJSON. The spec's `finalize_query` /
   `query_endpoint` code cannot be pasted in.
2. **Tracer lives server-side:** spec puts `ExecutionTracer` in the orchestrator and appends
   `trace_json` to `/query`. Reality: the orchestrator runs **inside the CLI subprocess**;
   the server never imports it. A trace must be emitted by `kitbash_cli.py` as NDJSON
   (`{"type":"trace_event",...}`), then forwarded verbatim by the server (already happens).
   A server-side tracer has no access to the in-flight query.
3. **`query_orchestrator.py`** wire target ⇒ retired to `attic/`; live is `query_orchestrator_posix.py`.
4. **`cartridge_loader.retrieve` / `mtr.rank` / `bitnet.generate` / `context_builder.build`** ⇒
   none exist. Real calls: `CartridgeInferenceEngine.query(request)`,
   `engines[layer].query(request)`, `mamba_service.get_context(request)`. The 4 trace points
   (cartridge/context/mamba/bitnet) are not at the API the spec sketches.
5. **`/trace/{query_id}` + session ID:** spec implies backend trace persistence. There is no
   session/trace store. `query_id` exists on `answer_done` (good correlation key) but nothing
   persists it. Spec itself marks persistence as future work.
6. **UI:** spec's HTML/JS is a from-scratch redesign (chat-history div, `tracebtn`, `displayTrace`).
   Real UI already exists; the achievable change is **additive** (append to `#answer` history,
   add `#tracebtn` + `#trace` pane, parse new `trace_event` NDJSON) — not a rewrite.
7. **Perf (<5% overhead):** real path is subprocess + buffered response; adding `trace_event`
   NDJSON lines is negligible.

## Feasible to build now (standalone, like CHUNK_RETRIEVAL approach)
- **`execution_tracer.py`** — the dataclass module (TraceEvent/ExecutionTracer) is buildable
  as-is; pure, no repo deps. Rename the *integration concept* to "TraceCollector used by the
  CLI" to kill the server-side misconception.
- **NDJSON trace emission in `kitbash_cli.py`** — record the steps the CLI can actually see:
  query entry, mamba context (from `result.mamba_injected` + any mamba metadata), engine
  cascade (from `result.layer_results`), final assembly. Emit `{"type":"trace_event", ...}`
  lines interleaved with the chat stream. This is the *correct* integration point.
- **Additive frontend** to `static/index.html`: in-session chat-history buffer + `#tracebtn`
  / `#trace` pane that parses `trace_event` lines. Real, contained UI task.
- **`kitbash_web.py`:** no server-side tracer needed (forwards NDJSON already). Optionally add
  a no-op `/trace` route returning the spec's "not implemented" JSON for future use.

## Blocked / needs decision
- **Server-side `ExecutionTracer` wired into the orchestrator** as the spec literally describes
  ⇒ impossible without re-architecting the subprocess server into an in-process one. Recommend:
  **emit trace via CLI NDJSON instead** (matches reality).
- **`context_builder` trace point** ⇒ needs the real context-assembly code located/refactored
  first; `QueryResult` does not currently expose the assembled context text. Defer or extend
  `QueryResult` deliberately.
- **`/trace/{query_id}` persistence** ⇒ needs a session/trace store that doesn't exist; defer
  (spec marks it future work).

## Recommendation
Build three independent, verifiable pieces (mirroring the CHUNK_RETRIEVAL execution):
  1. `execution_tracer.py` (dataclass module)
  2. Trace emission in `kitbash_cli.py` via NDJSON
  3. Additive frontend (chat history + trace pane) in `static/index.html`
Do **not** attempt the server-side-tracer / Flask sketch. See `docs/PLAN-WEBUI_TRACE_VISIBILITY.md`.
