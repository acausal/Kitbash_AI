# SPEC: Trace Chain Contract

**Date:** 2026-07-13
**Baseline commit:** `0a7bc27` (verify with `git log -1` before starting; STOP if HEAD differs)
**Status:** DRAFT — authorizes implementation in two phases (HARD STOP between them)
**Supersedes:** the ad-hoc per-query `chain` dict introduced by `LearningObserver._log_trace`
(B4 fix, commit `5092d86`) and the obsolete list-of-steps chain model still assumed by
`sleep_procedural_edge_extractor.py`.

## Purpose

Resolve the trace-chain shape mismatch that blocked `TASKS_POST_HARDENING_CLOSEOUT` **Task C
(STEP-0 GATE STOP)**: the trace **writer** emits `chain` as a per-query **dict**, but the
procedural-edge **extractor** parses it as a **list of step dicts** (`{fact_id, cartridge}`),
causing an `AttributeError` (or 0/garbage edges) and forcing the run to halt.

The fix is the long-flagged SOCKET_MAP item: **"define what a chain IS in one place both the
writer and the extractor import."** This spec defines that single source of truth and the
edge-extraction semantics derived from it.

## Canonical chain shape (single source of truth)

A trace `chain` is a **per-query summary dict** (NOT a list). Defined concretely as a
dataclass in `interfaces/trace_chain.py`:

```python
@dataclass
class TraceChain:
    query_id: str
    chain_type: str                 # "intra_query" today; "cross_query" reserved
    fact_ids: List[int]             # order NONDETERMINISTIC (set-sourced) — never rely on it
    grain_ids: List[str]            # may be empty
    confidence: float               # raw signal; NOT clamped here (see non-goals)

    def to_dict(self) -> dict: ...  # exact on-disk shape below
    @classmethod
    def from_dict(cls, d: dict) -> "TraceChain": ...  # tolerant; raises on missing query_id/fact_ids
```

On-disk `chain` dict (MUST match what `LearningObserver._log_trace` writes today, byte-for-byte
in keys — this is the contract the diagnostic already relies on):

```json
{
  "query_id": "76844644-957b-4745-9011-0b39f041f3e9",
  "chain_type": "intra_query",
  "fact_ids": [1],
  "grain_ids": [],
  "confidence": -8.618160247802734
}
```

Field rules:
- `fact_ids` is the **only** fact reference. There is no per-step `fact_id`. Edges are derived as
  **pairwise co-occurrence over `set(fact_ids)`** with canonical key `a<b` (see Edge-extraction
  semantics) — **order-dependent semantics (including consecutive pairs) are FORBIDDEN** because
  `fact_ids` order is nondeterministic (set-sourced).
- `grain_ids` is a flat list (currently always `[]` on live data — see Task B finding: 0% populated).
- `confidence` is the raw MTR signal; ranges routinely outside [0,1] (Task B: up to 8.77, down to
  -8.6). This contract does **not** normalize it.

## Edge-extraction semantics (derived from the canonical shape)

Both stages MUST consume `TraceChain` via the shared helpers — never by ad-hoc `chain[i].get(...)`.
`fact_ids` order is **nondeterministic** (set-sourced), so **all edge semantics are order-free**.

**Pairwise co-occurrence (the ONLY edge rule):** for one `TraceChain`, take `S = set(fact_ids)`.
For every unordered pair `{a, b}` with `a < b` (canonical key `a→b`), emit one edge
`edge_type="intra_cartridge"`, `source_cartridge == target_cartridge == winning cartridge of that
query` (carried on the trace record's `context.cartridge`, or `"unknown"` if absent).
- `fact_ids = [1, 3, 9]` → `set = {1,3,9}` → edges **`1→3`, `1→9`, `3→9` (3 edges)**.
- `fact_ids = [1]` (single fact, the ENTIRE live corpus today) → **0 edges**. This is CORRECT, not
  a bug: a one-fact query has nothing to connect. The graph will be empty until the corpus carries
  multi-fact queries. The remediation is **usage accumulation, not code** (stated explicitly so an
  empty graph is not mistaken for a failure).

**Cross-query / session edges: OUT OF SCOPE (deferred ticket).** Removed from this spec. Any
order-independent cross-query edge also depends on deterministic fact_ids ordering and on a corpus
that has multi-query sessions — neither holds today. **Deferred ticket:** *"cross-query/session
edges — resume when fact_ids ordering is deterministic and corpus has multi-query sessions."*

Shared helper signature (in `interfaces/trace_chain.py`):
```python
def iter_cooccurrence_edges(chain: TraceChain, cartridge: str):
    # yields (source_fact, target_fact) for every unordered pair a<b in set(fact_ids)
    # order-independent; never consecutive-pair
```

## Scope

### Phase 1 — shared contract + tests (no behavior change)
- Add `interfaces/trace_chain.py`: `TraceChain` dataclass + `to_dict`/`from_dict` + the two
  `iter_*` helpers. Pure-additive; touches no existing runtime path.
- Add `tests/TEST-trace_chain_contract.py` asserting:
  1. `TraceChain(...).to_dict()` equals the exact on-disk dict shape above.
  2. `from_dict` round-trips; raises on missing `query_id`/`fact_ids`.
  3. `iter_cooccurrence_edges` on `[1,3,9]` yields **3 edges** `1→3`, `1→9`, `3→9` (all `a<b`).
  4. `iter_cooccurrence_edges` on `[1]` yields **0** edges (thin-corpus correctness).
  5. `iter_cooccurrence_edges` is order-independent: `[9,1,3]` yields the same 3 edges as `[1,3,9]`.
- **DONE WHEN (Phase 1):** `python tests/TEST-trace_chain_contract.py` → all PASS. Same commit:
  SOCKET_MAP note that the chain contract module now exists (no status flip yet).
- **HARD STOP** after Phase 1.

### Phase 2 — wire writer + extractor to the shared contract
- `learning_observer.py` `_log_trace`: build `chain` via `TraceChain(...).to_dict()` (logic
  unchanged — same keys/values; only the construction site moves to the shared class).
- `sleep_procedural_edge_extractor.py`: replace the list-of-steps parsing (lines ~112-175) with
  `TraceChain.from_dict(trace["chain"])` + `iter_cooccurrence_edges`. **Stage 2.5 (cross-query
  edges) is removed from scope** — do NOT port it; the extractor's `extract_cross_cartridge_edges`
  becomes a no-op stub (or is deleted) and any cross-cartridge edge type is no longer produced. A
  dry `SleepOrchestrator.run_stage_1_5()` over live `traces.jsonl` produces the graph with no crash.
- **DONE WHEN (Phase 2):** `python tests/TEST-trace_chain_contract.py` still PASS; a dry
  `SleepOrchestrator.run_stage_1_5()` over live `traces.jsonl` produces a
  `procedural_edge_graph.json` that loads back via `RecalibrationService._load_edge_graph()`
  (read-only check). Edge count may be 0 (thin corpus) — that is GREEN, not RED. Same commit:
  SOCKET_MAP §5 follow-up (a) → CLOSED (graph built); cell stays YELLOW until Isaac's `mtr_error`
  calibration decision (Task B) lands, because **live Stage 5 recalibration is still gated** — this
  spec only builds the graph, it does NOT run recalibration.

## Non-goals (scope-lock)
- Do NOT change the dissonance gate (`mtr_error > 0.5`) or add any normalization/clamping to
  `confidence` (Task B calibration decision is Isaac's).
- Do NOT run Stage 5 / `run_recalibration_cycle()` or the full sleep pipeline — that reaches
  Stage 5 and is gated on Isaac's decision. This spec only builds the intra-query edge graph
  (Stage 1.5). Stage 2.5 (cross-query edges) is removed from scope — deferred ticket:
  *"cross-query/session edges — resume when fact_ids ordering is deterministic and corpus has
  multi-query sessions."*
- Do NOT modify `DIAGNOSTIC-trace_signal_check.py` (already reads `chain` correctly as a dict).
- Do NOT alter `context["mamba_context"]` serialization (separate, completed spec).
- Do NOT invent multi-fact synthetic data to force a non-empty graph. Empty graph on a
  single-fact corpus is the correct, expected result.

## HARD STOP
Between Phase 1 and Phase 2. After Phase 2. First **live** recalibration run (Stage 5) is a future
task authorized only after Isaac's `mtr_error` calibration decision.

## SOCKET_MAP impact
- §5 Violation-schema cell, follow-up (a): OPEN today. Phase 2 closes it (graph built). Cell stays
  YELLOW — remaining gate is the mtr_error calibration decision (Task B → Isaac) before Stage 5.
- The "define what a chain IS in one place both writer and extractor import" pending item is
  RESOLVED by this spec's `interfaces/trace_chain.py`.
