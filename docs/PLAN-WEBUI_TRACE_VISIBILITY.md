# PLAN: WebUI & Execution Trace Visibility v1 (feasible slice)

**Grounded in:** `docs/DEVNOTE-WEBUI_AND_TRACE_VISIBILITY.md` (audit, 2026-07-15)
**Anti-pattern avoided:** the spec's server-side `ExecutionTracer` + Flask sketch. The real
system is `kitbash_web.py` (stdlib http.server, subprocess) → `kitbash_cli.py` (orchestrator in
a subprocess, emits NDJSON on stdout). So **the CLI is the trace collector**, and the server
just forwards NDJSON it already forwards.

## Scope (this plan)
Three independent, verifiable pieces. UI is a chat-POC; keep changes additive to the existing
`static/index.html` (no rewrite). No server-side tracer, no `/trace` persistence (deferred).

- [x] **P1. `execution_tracer.py`** (new, repo root, core) — pure dataclass module. `a12587d`
- [x] **P2. Trace emission in `kitbash_cli.py`** — use P1 to emit `trace_event` NDJSON. `fb77562`
- [x] **P3. Additive frontend** in `static/index.html` — chat history + trace pane. `9fa41ce`

Deferred (per DEVNOTE): server-side tracer, `context_builder` point (needs `QueryResult`
extension), `/trace/{query_id}` persistence.

---

## P1 — `execution_tracer.py` (repo root)

Pure module, no repo imports. Adapt the spec's `TraceEvent`/`ExecutionTracer` verbatim (it's
correct and dependency-free), but rename the consumer concept to a CLI-side collector.

API:
```python
@dataclass
class TraceEvent:
    step_name: str          # "query_entry" | "mamba_context" | "engine_cascade" | "final_assembly"
    timestamp: str          # ISO 8601 (datetime.now().isoformat())
    input: dict
    output: dict
    duration_ms: int
    metadata: dict = field(default_factory=dict)

class ExecutionTracer:
    def trace(self, step_name, input_data, output_data, duration_ms, metadata=None) -> None
    def events(self) -> list[TraceEvent]
    def to_json(self) -> str                       # [asdict(e) for e in events]
    def clear(self) -> None
```
Verification: ad-hoc gate — construct tracer, add 2 events, assert `to_json()` parses,
`clear()` empties. (Pure module; no orchestrator needed.)

Commit: `core: execution_tracer.py (TraceEvent + ExecutionTracer)`

---

## P2 — Trace emission in `kitbash_cli.py`

`handle_query` already has `result` (QueryResult) + `t0`. Wrap the call in a tracer and emit
`{"type":"trace_event", ...}` NDJSON lines interleaved with the chat stream (server forwards
them unchanged). Use the data actually available on `result` (no orchestrator refactor):

```python
def handle_query(orchestrator, user_query: str) -> None:
    tracer = ExecutionTracer()
    t0 = time.perf_counter()

    # Step 1: query entry
    tracer.trace("query_entry", {"query": user_query}, {"query_len": len(user_query)}, 0,
                 {"note": "entered handle_query"})

    result = orchestrator.process_query(user_query)
    total_ms = (time.perf_counter() - t0) * 1000

    # Step 2: mamba context (what we can see on result)
    tracer.trace("mamba_context",
                 {"query": user_query},
                 {"mamba_injected": getattr(result, "mamba_injected", False)},
                 _ms_since(t0),
                 {"note": "from QueryResult.mamba_injected"})

    # Step 3: engine cascade (from result.layer_results)
    tracer.trace("engine_cascade",
                 {"query": user_query},
                 {"layers": [{"engine": a.engine_name, "confidence": a.confidence,
                              "passed": a.passed, "latency_ms": a.latency_ms}
                             for a in (result.layer_results or [])]},
                 _ms_since(t0),
                 {"num_layers": len(result.layer_results or [])})

    # Step 4: final assembly
    tracer.trace("final_assembly",
                 {"engine": result.engine_name, "confidence": result.confidence},
                 {"answer_len": len(result.answer or "")},
                 round(total_ms, 1),
                 {"total_latency_ms": round(total_ms, 1)})

    # Emit trace events as NDJSON (BEFORE answer_done so UI can capture them).
    for ev in tracer.events:
        _emit_stdout({"type": "trace_event", **asdict(ev)})

    # ... existing answer_chunk streaming + answer_done (unchanged) ...
```

Notes / guardrails:
- `trace_event` lines go on **stdout** (chat channel) so the browser gets them; the server
  already forwards stdout verbatim. (Ops detail stays on stderr per CLI contract.)
- `result.layer_results` is the real field (QueryResult.line 72). No `cartridge_loader.retrieve`
  / `context_builder` calls — those don't exist; cartridge/fact detail would require extending
  `QueryResult` (deferred).
- Graceful: if `result.layer_results` is absent, emit empty list (don't crash).
- Keep `answer_done` shape unchanged (UI compatibility).

Verification: ad-hoc gate — run `kitbash_cli` logic against a stub orchestrator returning a
fake `QueryResult` (with 2 `LayerAttempt`s), assert stdout contains 4 `trace_event` lines with
correct `step_name`s and a parseable `answer_done`. (Subprocess spawn is slow; prefer importing
`handle_query` with a fake orchestrator in the gate.)

Commit: `core: emit trace_event NDJSON from kitbash_cli (4 steps from QueryResult)`

---

## P3 — Additive frontend in `static/index.html`

Two additive features; do NOT rewrite the existing send/OPS flow.

**(a) In-session chat history** (Part 1 of spec):
- Add `<div id="chat-history">` above the input row (max-height ~400px, scroll).
- In-memory `messageBuffer = []`; `addMessage(role, content, meta)` appends + re-renders.
- In `send()`: `addMessage('user', text)` immediately; on `answer_done`, `addMessage('assistant', answerText, metaHTML)`.
- Preserve existing OPS toggle + NDJSON parse; just also append to history.

**(b) Trace pane** (Part 2 of spec):
- Add `<button id="tracebtn">Toggle Debug Trace</button>` + `<pre id="trace">` (hidden).
- Collect `trace_event` lines during the fetch loop into a `currentTrace` array.
- On `tracebtn` click, render `currentTrace` as collapsible sections (step_name + duration_ms +
  JSON body) into `#trace`. Toggle display.
- Keep CSS minimal, matching existing dark `#ops` style.

Verification: manual (serve `kitbash_web.py`, open browser) + a headless check that `#trace` /
`#chat-history` elements exist in the HTML and the new JS parses `trace_event` (can lint the
script block with `node --check` if node present, else manual). No automated DOM test harness
exists; mark as manual-verify + code review.

Commit: `ui: static/index.html add session chat history + debug trace pane`

---

## Execution order & verification convention
- Build P1 → verify (ad-hoc gate) → commit.
- Build P2 → verify (ad-hoc gate w/ fake orchestrator) → commit.
- Build P3 → manual verify → commit.
- One piece per commit (KISS/DRY, scoped). Each verified by an ad-hoc `hermes-verify-*` gate
  (deleted after), summarized as ad-hoc (not suite green), per project guardrail.

## Open questions for Isaac (from spec Notes, still valid)
1. Chat history cap (suggest 100 msgs/session)?
2. Trace detail configurable (top-5 grains etc.) — blocked until `QueryResult` exposes grains.
3. Trace export button — defer to Phase 4.
4. Tag traces with `query_id` — already on `answer_done`; can mirror into `trace_event.metadata`.
