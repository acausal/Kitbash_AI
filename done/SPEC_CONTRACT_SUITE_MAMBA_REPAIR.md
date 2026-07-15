# SPEC: Orchestrator Contract Suite Repair + Serializable Mamba Context Entry

**Date:** 2026-07-12
**Baseline commit:** `5a7ef41` (verify with `git log -1` before starting; STOP if `query_orchestrator_posix.py`, `tests/TEST-orchestrator_contract.py`, or `interfaces/mamba_context_service.py` changed since)
**Parent findings:** 2026-07-12 review follow-up — pre-existing line-206 contract-suite break (independently reproduced on clean `0978672`)
**Approval note:** Isaac has approved the Phase 2 orchestrator touch. It is telemetry-only: line 206 / Pattern A prompt injection is UNTOUCHED, `context["mamba_context"]` has zero readers (grep-verified), answers and routing are byte-identical. The routing/answer approval gate is satisfied for exactly the change specified in Phase 2 and nothing beyond it.
**Socket map cells:** §6 Orchestrator contract suite (stale GREEN — measured failing), §1 Query entry (evidence line cites 23/23 — stale)

---

## Context (read, do not act on)

`TEST-orchestrator_contract.py` currently crashes at test #1:
`AttributeError: 'dict' object has no attribute 'context_1hour'`
(`query_orchestrator_posix.py:206`). Root cause: Pattern A (2026-07-11)
consumes `mamba_context.context_1hour` by attribute; the suite's two mamba
stubs (in `build_orchestrator`: the `mamba_service` lambda and the
`orch._get_mamba_context` monkeypatch) return plain `{}` dicts, violating the
ratified `MambaContext` interface (`interfaces/mamba_context_service.py`,
which guarantees "never None, empty-but-valid"). The suite was not re-run
after Pattern A landed, so the map's 23/23 GREEN went stale silently.

With corrected stubs the suite reaches 21/23 (sandbox run). The two
remaining failures:

- **#7 factory coherence** — "No cartridges loaded successfully." Likely a
  sandbox-environment artifact; must be classified on real hardware in
  Phase 1.
- **#8 trace context JSON-serializable** — real. Orchestrator line 198 stores
  the raw `MambaContext` dataclass into `context["mamba_context"]`; the
  contract requires the query context to stay JSON-serializable.

Two fields of `MambaContext` are serialization-hostile **by construction**,
not just in theory:

1. `hidden_state: Optional[bytes]` — bytes; always `None` today, will
   populate when stateful memory lands (SPEC §2b D2).
2. `conversation_history: List[Message]` — `Message.__post_init__` FORCES
   `timestamp = datetime.now()` when None, so any populated history carries
   a `datetime`, which `asdict()` preserves and `json.dumps` rejects.

Both are empty on today's live path — i.e. the current code is
serializable-by-current-luck. This spec makes it serializable by
construction and makes the contract able to prove it.

---

## Non-goals (touching any of these is a spec violation — STOP and report instead)

1. Do NOT touch line 206 / the Pattern A prompt-injection block, triage,
   cascade order, thresholds, or anything that changes engine-visible text
   or routing. The approval above covers Phase 2's line-198 change ONLY.
2. Do NOT modify `interfaces/mamba_context_service.py` (no `to_dict` method,
   no field changes — interface is ratified).
3. Do NOT weaken, remove, or add tolerance to test #8's `json.dumps`
   assertion, and do NOT coerce with `default=str` anywhere (silent
   stringification hides the next hostile field — fail-loud principle).
4. Do NOT fix test #7 if it fails on real hardware. Classify it, file a
   discovery ticket in the commit message, STOP and report. Scope-lock.
5. Do NOT modify `TEST-orchestrator_e2e.py`, `mock_mamba_service.py`, or
   `real_mamba_service.py`.
6. Do NOT create files beyond the deliverables named below.

---

## Phase 1 — Repair the suite's mamba stubs (test file only)

**Deliverable:** modified `tests/TEST-orchestrator_contract.py` only.

### Steps (in order)

1. Import the real interface type at the top of the test:
   `from interfaces.mamba_context_service import MambaContext, Message`.
2. Define ONE module-level stub factory (both stub sites must use it —
   single source of truth):

   ```python
   def _stub_mamba_context() -> MambaContext:
       # context_1hour DELIBERATELY EMPTY: Pattern A must inject nothing in
       # this harness, so augmented_query == user_query and the other
       # assertions see unchanged engine-visible text.
       # hidden_state + conversation_history DELIBERATELY POPULATED: these
       # are the two serialization-hostile fields (bytes; forced datetime).
       # Test #8 must prove the orchestrator sanitizes them — not pass
       # vacuously on an empty dataclass. If MambaContext ever gains a new
       # field, populate it here so the contract can see it.
       return MambaContext(
           hidden_state=b"\x01",
           conversation_history=[Message(role="user", content="harness msg")],
           active_topics=["harness"],
       )
   ```

3. Replace both stale stubs in `build_orchestrator`:
   - `mamba_service=type("M", (), {"get_context": lambda *a, **k: _stub_mamba_context()})(),`
   - `orch._get_mamba_context = lambda *a, **k: _stub_mamba_context()`
4. No assertion changes anywhere. Test #8 stays byte-identical.

### DONE WHEN (paste executed output — reading is not verification; run on real hardware, not a container)

1. `python tests/TEST-orchestrator_contract.py` executed. Expected shape:
   - The #1 AttributeError crash is GONE; tests #1–#6 PASS.
   - **#8 FAILS** (`MambaContext` object still stored raw at line 198) —
     this is the bridging RED that Phase 2 turns green. If #8 passes in
     Phase 1, something is wrong: STOP and report.
   - **#7 classified:** if it PASSES on real hardware → sandbox artifact,
     note it and move on (expected total 22/23 with only #8 red). If it
     FAILS on real hardware → new pre-existing discovery: paste output,
     file ticket in commit message, do NOT fix, proceed (expected 21/23).
2. Paste the full run either way.

### Same-commit obligations (map rule 1 — the map currently lies)

- `SOCKET_MAP.md` §6 "Orchestrator contract suite" cell: correct from stale
  GREEN to measured state (crash was measured on clean `0978672`; after this
  phase, suite runs with #8 RED pending Phase 2 — record the actual count).
- §1 Query entry cell: annotate the "23/23 PASS" evidence line as stale as
  of Pattern A (2026-07-11), corrected this session.

### HARD STOP

Report Phase 1 output (including the #7 classification) and commit Phase 1
alone. Await go-ahead unless Isaac has pre-authorized continuous execution
of this spec.

---

## Phase 2 — Serializable `context["mamba_context"]` (orchestrator only)

**Deliverable:** modified `query_orchestrator_posix.py` only.

### Steps (in order)

1. Add a module-level helper (near the other small helpers):

   ```python
   from dataclasses import asdict

   def _serializable_mamba_context(mc) -> dict:
       """JSON-safe projection of MambaContext for the query context dict.

       The query context is a serializable-by-contract surface (T7 #8).
       - hidden_state (bytes) is EXCLUDED: engine plumbing, not context
         signal.
       - conversation_history Message timestamps (datetime, forced non-None
         by Message.__post_init__) are converted to ISO-8601 strings.
       Everything else passes through asdict() untouched. This dict is the
       Pattern B (routing-aware) entry point — rehydrate or read as needed.
       """
       if mc is None:
           return {}
       d = asdict(mc)
       d.pop("hidden_state", None)
       for m in d.get("conversation_history", []):
           ts = m.get("timestamp")
           if ts is not None and not isinstance(ts, str):
               m["timestamp"] = ts.isoformat()
       return d
   ```

2. Change line 198 from
   `context["mamba_context"] = mamba_context`
   to
   `context["mamba_context"] = _serializable_mamba_context(mamba_context)`.
3. NOTHING ELSE CHANGES. Line 205–210 (Pattern A) still reads the local
   `mamba_context` object. `QueryResult.mamba_injected` logic untouched.

### DONE WHEN (paste executed output for ALL of the following; real hardware)

1. `python tests/TEST-orchestrator_contract.py` → #8 PASS. Expected total:
   23/23 if #7 was classified as sandbox artifact in Phase 1, else 22/23
   with #7 as the ticketed known-fail. Paste full run.
2. `python tests/TEST-orchestrator_e2e.py` → 10/10 PASS (real torch) — the
   answer-path proof backing the approval note: answers, engines, and
   `mamba_injected` behavior unchanged.
3. `python tests/TEST-learning_observer.py` → all PASS (report/trace shapes
   downstream of context untouched).
4. Ad-hoc scriptlet (paste it + output): build the Phase 1 stub context via
   `_stub_mamba_context()`, run it through `_serializable_mamba_context`,
   `json.dumps` the result — succeeds; confirm `"hidden_state"` absent and
   the history timestamp is a string.

### Same-commit obligations

- `SOCKET_MAP.md` §6 Orchestrator contract suite cell → GREEN with the new
  executed count + date; §1 Query entry evidence line updated to match.
  If #7 remains red, the cell notes it as the single ticketed known-fail
  (measured, out of scope) rather than claiming a clean sweep.
- Discoveries out of scope → commit-message ticket, not spec extension.

### HARD STOP

Report Phase 2 output and stop. The signal-validation run and the Stage 1.5
live edge-graph build remain separate, unauthorized tickets.
