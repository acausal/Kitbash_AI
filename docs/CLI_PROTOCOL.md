# Kitbash CLI Protocol

Stdio JSON bridge for the query orchestrator. The web UI spawns
`kitbash_cli.py` as a child process and talks to it over three streams:

| Stream  | Carries                         | Purpose                       |
|---------|---------------------------------|-------------------------------|
| stdin   | requests (JSON, one per line)   | UI → Kitbash                  |
| stdout  | **chat only** (JSON)            | Kitbash → UI (clean)          |
| stderr  | ops / logs / internal streams   | debugging + telemetry (UI tails this) |

The chat/stderr split is a hard contract: **stdout must never contain
operational text** (engine logs, MTR banner, stack traces). Those go to stderr.

## Request (stdin)

One JSON object per line:

```json
{"query": "What is entropy?"}
```

| field   | type   | required | notes                              |
|---------|--------|----------|------------------------------------|
| query   | string | yes      | non-empty; else `error` returned   |

Unknown fields are ignored. Malformed JSON (not parseable) → `error` line,
no crash.

## Response (stdout)

Newline-delimited JSON. For one query, a sequence of `answer_chunk`
objects followed by exactly one `answer_done` (or one `error`):

```json
{"type":"answer_chunk","text":"The Correspondence"}
{"type":"answer_chunk","text":"Theory of Truth"}
{"type":"answer_done","query_id":"990aa35a-...","engine":"CARTRIDGE","confidence":0.75,"total_latency_ms":5215.5}
```

| type           | fields                                              | meaning                                  |
|----------------|-----------------------------------------------------|------------------------------------------|
| `answer_chunk` | `text` (string)                                     | v1 fake-streamed piece of the answer     |
| `answer_done`  | `query_id`, `engine`, `confidence`, `total_latency_ms` | final: which engine answered + score |
| `error`        | `message` (string)                                  | bad request / query failure              |

- `answer_chunk` pieces are word-ish splits of the final answer (v1
  "fake streaming"); the UI concatenates them. Real token streaming drops
  in later at the engine layer without changing this wire format.
- `engine` is the winner-take-all cascade result (CARTRIDGE / BITNET / …).

## Ops channel (stderr)

Plain Python logging, e.g.:
```
2026-07-11 16:59:03,931 INFO kitbash_cli: kitbash_cli starting; building orchestrator...
2026-07-11 16:59:04,179 INFO query_orchestrator_factory:   ✓ MTREngine initialized
...
2026-07-11 16:59:29,881 INFO root: query=be21aafc engine=CARTRIDGE conf=0.750 latency_ms=15326.7 layers=2
```
Internal only — the UI should not parse this for chat, but may surface it
for a debug/telemetry pane.

## Lifecycle

- The CLI reads requests from stdin until **EOF**, then exits cleanly.
- The UI owns the child process (start on session open, close stdin / kill
  on session end).
- BitMamba2 server is **autostarted** by the CLI if not already running
  (on the configured port) and is a separate process.

## Configuration (env vars)

| var                      | default | effect                                  |
|--------------------------|---------|-----------------------------------------|
| `KITBASH_ENABLE_BITNET`  | `1`     | set `0` to disable the BitNet engine   |
| `KITBASH_ENABLE_MAMBA`   | `1`     | set `0` to disable BitMamba2 context   |
| `KITBASH_BITNET_URL`     | `http://127.0.0.1:8080` | BitNet server URL (bitnet_engine.py) |

## Running

```bash
.venv\Scripts\activate
echo {"query":"hello"} | python kitbash_cli.py
# chat JSON on stdout; ops on stderr
```

Contract is locked by `TEST-kitbash_cli.py` (3/3 PASS): stdout chat-only +
no ops leakage, malformed/missing-query → error line, no crash.
