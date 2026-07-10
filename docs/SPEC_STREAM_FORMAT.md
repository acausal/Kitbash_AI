# SPEC — Intentional Data Stream Format (Kitbash Bus Plane)

**Status:** DRAFT / contract-first. Written before RedisBlackboard wiring per SOCKET_MAP.md Phase-5 blocker #2.
**Date:** 2026-07-10
**Scope:** Defines the on-the-wire envelope, per-namespace payload schemas, fact-injection format, epistemic-snapshot serialization, and TTL/archival policy for every value on the Redis bus. This is the contract that RedisBlackboard wiring, the grain registry, and all future bus plug-ins implement against.

Grounded in the current code: `redis_blackboard.py` (`RedisBlackboard`), `redis_coupling.py` (`CouplingDelta`, `CouplingValidator`), `MTR_v6_1.py` (`get_epistemic_snapshot`). Where this spec differs from current behavior, the difference is called out explicitly as a **GAP** with a migration note — the spec is the target, not a description of today.

---

## 0. Why this exists

The bus is a socket factory: components attach by reading/writing agreed keys instead of by orchestrator surgery. That only works if every value on the bus is self-describing and versioned. Today it is not:

- **GAP-1 (namespace):** `redis_coupling.py` writes `query:{query_id}:deltas` (lines 145, 292) — outside the `kitbash:` prefix every other producer uses. A consumer scanning `kitbash:*` never sees coupling deltas. **Target:** `kitbash:coupling:{query_id}:deltas`.
- **GAP-2 (versioning):** no payload carries a schema version. A v2 producer and a v1 consumer cannot detect the mismatch; they silently misread. This is exactly how v6 happened. **Target:** every value is wrapped in the versioned envelope below.
- **GAP-3 (TTL):** `health` expires at 300s; `queries:state`, `grains`, `metrics`, and coupling deltas have no TTL and grow unbounded (only `cleanup_old_queries` is manual). **Target:** every namespace declares a TTL/archival policy (§4).

---

## 1. The envelope (applies to every value)

Every value written to the bus — string, hash field, or list element — is a JSON object with a fixed outer shape. Payload-specific fields live under `data`.

```json
{
  "v": 1,                          // envelope version (this document = 1)
  "schema": "query_state@1",       // "<payload_name>@<payload_schema_version>"
  "produced_at": "2026-07-10T12:00:00.000000",  // ISO-8601, UTC, µs precision
  "producer": "orchestrator",      // component id (matches kitbash:<producer>: namespace)
  "data": { ... }                  // payload; schema named by the `schema` field
}
```

Rules:
- **`v`** gates the envelope grammar. A consumer that does not recognize `v` MUST refuse the value loudly (raise / log_error), never best-effort parse. No `dict.get` soft-fail on the envelope.
- **`schema`** is `name@N`. `name` selects the payload validator; `N` is bumped on any breaking payload change. Additive-only changes (new optional field) do NOT bump `N`; removals/renames/type-changes DO.
- **`produced_at`** is UTC ISO-8601 (matches the existing `datetime.now().isoformat()` sites, but UTC-normalized — current code uses naive local time, a latent GAP).
- **`producer`** MUST equal the component's declared namespace segment (§3), so provenance is recoverable from the value alone.
- List elements (`diagnostic:feed`, coupling deltas, queue) are each individually enveloped. The queue is the one exception: it holds bare `query_id` strings (pointers, not payloads) — see §3.2.

---

## 2. Payload schema registry

Each payload has a name, a version, and an owner. Bumping a version requires updating this table and the owning component's contract test.

| Payload name | Ver | Owner (producer) | Written to |
|---|---|---|---|
| `query_state` | 1 | orchestrator | `kitbash:queries:state:<id>` |
| `grain` | 1 | grain_registry | `kitbash:grains:<fact_id>` |
| `diagnostic_event` | 1 | any (via feed) | `kitbash:diagnostic:feed` |
| `worker_health` | 1 | each worker | `kitbash:health:<worker>` |
| `metric_point` | 1 | any | `kitbash:metrics:<name>` |
| `coupling_delta` | 1 | coupling_validator | `kitbash:coupling:<query_id>:deltas` |
| `epistemic_snapshot` | 1 | mtr | `kitbash:epistemic:<query_id>` |

---

## 3. Namespaces & payload shapes

All keys are prefixed `kitbash:` (configurable via `RedisBlackboard(prefix=...)`, default `kitbash:`). A component owns exactly one segment: `kitbash:<component>:...`.

### 3.1 `queries:state:<query_id>` — STRING(enveloped JSON), payload `query_state@1`
Mirrors the current `create_query`/`update_query_status` dict:
```json
{ "query_id": "...", "query_text": "...", "status": "pending|started|layerN_*|completed|failed",
  "created_at": "...", "started_at": null, "completed_at": null,
  "layer_attempts": [ { "timestamp": "...", "result": { ... } } ],
  "metadata": { } }
```
`status` is an open string today; the spec pins the allowed set above. Unknown status = loud reject.

### 3.2 `queries:queue` — LIST of bare `query_id` strings (NOT enveloped)
Pointers into `queries:state:*`. LPUSH producer / RPOP consumer (FIFO), matching current code. Rationale: the queue carries no payload, only references; enveloping pointers adds nothing. This is the single documented exception to §1.

### 3.3 `grains:<fact_id>` — HASH, payload `grain@1` (the fact-injection format)
Current code stores hash fields `data` (JSON) + `updated_at`. Target: `data` holds the enveloped `grain@1` payload; `updated_at` stays a bare ISO string for cheap sorting.
```json
// grain@1 data
{ "grain_id": "...", "fact_id": "...", "cartridge_id": "...",
  "confidence": 0.0, "epistemic_level": "L2_AXIOMATIC",
  "text": "",                       // concept content — consumed by GrainRouter.search_grains overlap scoring
  "delta": { "positive": [], "negative": [], "void": [] },
  "quality_metrics": { } }
```
**Note (fact-injection ↔ grain registry contract):** the `text` field is what `search_grains` token-overlap scoring reads (fixed 2026-07-10). On-disk grains today lack `text`; adding it is a **grain-registry-format-contract** decision (adjacent Phase-5 cell), NOT settled here. This spec only fixes the *bus envelope*; the disk grain schema is decided on its own terms in that cell. Listed here so the two contracts stay compatible.

### 3.4 `diagnostic:feed` — LIST (capped 10 000), payload `diagnostic_event@1`
```json
{ "event_type": "layer_attempt|timeout|escalation|...", "query_id": "...", "details": { } }
```
Trim policy unchanged (`ltrim 0 9999`). See §4 for the archival hook.

### 3.5 `health:<worker>` — STRING(enveloped JSON), payload `worker_health@1`, TTL 300s
```json
{ "worker_name": "...", "status": "healthy|degraded|dead", "last_heartbeat": "...", "details": { } }
```
The one namespace with a correct TTL today. Keep `ex=300`.

### 3.6 `metrics:<name>` — ZSET (score = unix ts, member = value)
Member is a bare stringified float (NOT enveloped) — ZSET members must be unique/comparable; an envelope would break dedup and range scans. Provenance for metrics is the key name. This is the second documented envelope exception.

### 3.7 `coupling:<query_id>:deltas` — LIST, payload `coupling_delta@1`  ← **GAP-1 fix**
Moves `redis_coupling.py`'s `query:{id}:deltas` under the prefix. Payload = current `CouplingDelta.to_json()` fields (already a clean dataclass — good model), wrapped in the envelope:
```json
{ "query_id": "...", "layer_a": "L0..L5", "layer_b": "...", "status": "OK|FLAG|FAIL",
  "delta_magnitude": 0.0, "severity": "PASS|LOW|MEDIUM|HIGH|CRITICAL",
  "coupling_constant": 1.0, "timestamp": 0, "fact_a_id": null, "fact_b_id": null, "reasoning": "" }
```
The Lua `record` script (redis_coupling.py:145) and the Python reader (:292) both change key. **Migration:** dual-read (new key, fall back to legacy `query:{id}:deltas`) for one release, then drop the fallback.

### 3.8 `epistemic:<query_id>` — STRING(enveloped JSON), payload `epistemic_snapshot@1`
Serialization of `KitbashMTREngine.get_epistemic_snapshot(...)` output (today returned in-process, never persisted). The router returns a dict keyed by layer name → (vector-or-scalar, salience). Serialized form flattens to salience floats (the vectors stay in-process; only the epistemic summary crosses the bus):
```json
{ "query_id": "...", "layer_names": ["L0_ground_truth", "L2_heuristic", "L4_hat", ...],
  "salience": { "L0_ground_truth": 0.0, "L2_heuristic": 0.0, "L4_hat": 0.0 },
  "kappa": 1.0, "mtr_state_time": 0 }
```
Layer names are sourced from the single-source-of-truth `MTR_v6_1.LAYER_NAMES` (see the Epistemic-layer-names socket) — consumers MUST NOT hardcode them.

---

### 3.9 Procedural edges — deferred payload (NOT specified here)

`context_tag`/`hat_tag` fields: **NOT INCLUDED.** Empirical check to justify them could not run — sleep pipeline currently produces single-fact chains with null hat (writer/extractor chain-shape mismatch, likely the same issue as Sleep Plane B4 in SOCKET_MAP.md). Revisit this field decision once that's fixed and the empirical check can actually run. Do not add these fields speculatively before then.

## 4. TTL & archival policy  ← **GAP-3 fix**

| Namespace | TTL | Archival on expiry/trim |
|---|---|---|
| `queries:state:<id>` | 24h (refresh on update) | none — terminal state is derivable from feed |
| `queries:queue` | n/a (drained by workers) | dead-letter to `kitbash:queries:dead` after N failed dequeues |
| `grains:<fact_id>` | none (durable index) | mirror of disk registry; rebuildable |
| `diagnostic:feed` | count-capped 10 000 | trimmed events flushed to dream bucket / cold log before drop |
| `health:<worker>` | 300s | none — absence = dead |
| `metrics:<name>` | 7d rolling (ZREMRANGEBYSCORE on write) | roll up to daily aggregate before prune |
| `coupling:<id>:deltas` | 24h (matches Lua `EXPIRE` at redis_coupling.py:151) | none |

`queries:state` gaining a 24h TTL replaces the manual `cleanup_old_queries(hours=24)` — same window, now automatic and refreshed on every `update_query_status`.

---

## 5. Versioning & migration

- **Additive** (new optional field): no version bump; old consumers ignore unknown keys — but only INSIDE `data`, never in the envelope.
- **Breaking** (remove/rename/retype): bump `name@N`, register the new version in §2, and either (a) dual-write both versions for one release, or (b) run a one-shot migrator. Consumers pin the max `N` they understand and loud-reject higher.
- Envelope `v` bump is reserved for changing the outer grammar itself and requires updating every producer/consumer in lockstep.

---

## 6. DONE WHEN (this spec's exit criteria → flips the socket GREEN)

1. `redis_blackboard.py` wraps/unwraps the §1 envelope on every read/write; unknown `v`/`schema` loud-rejects.
2. `redis_coupling.py` writes `kitbash:coupling:<id>:deltas` (GAP-1), envelope-wrapped, with legacy dual-read.
3. TTLs from §4 applied at write sites.
4. A contract test (`TEST-bus_stream_format.py`) runs against `fakeredis`: for every payload in §2, round-trips value → envelope → value, asserts version gating (a v2 value is rejected by a v1 consumer), and asserts every produced key is under `kitbash:`.
5. This file moves from DRAFT to RATIFIED; SOCKET_MAP "Intentional data stream format" cell → GREEN.

Until #1–#5 land, the cell is YELLOW (specified, not wired) — up from RED (unspecified).
