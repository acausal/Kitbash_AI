# episode_annotation_tool

Mark exploratory (`expl`) vs. action (`act`) episode boundaries so Dream Bucket
can build queryable dependency graphs during sleep (per `BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION.md`
and `SPEC-episode_annotation_tool_v1.md`).

## Functions

| Function | Purpose |
|----------|---------|
| `annotate_episode(phase, summary, session_id=None, query_id=None, agent_context=None, log_path=None, writer=None)` | Mark a boundary; return record |
| `read_episodes(log_path)` | Read back all episode records (JSONL) |
| `generate_episode_id(phase)` | `f"{phase}_{YYYYmmdd_HHMMSS}_{uuid8}"` (SPEC format) |

`phase` must be `"expl"` or `"act"`. Invalid phase / empty summary returns
`{"status":"error","reason":...}` (tool-level, never raises). Output schema
matches the SPEC record exactly: `episode_id, phase, summary, timestamp,
session_id, query_id, agent_context`.

## Isolation note

The SPEC postcondition is "append to `dream_bucket/live/episodes.jsonl` via
`DreamBucketWriter`". Importing `dream_bucket.py` would violate the `tools/`
Isolation Contract (no Kitbash core imports), so this tool writes the record as
JSONL to a configurable `log_path` (default `dream_bucket/live/episodes.jsonl`)
using only stdlib. The record format is drop-in compatible with the real
Dream Bucket `episodes` log type. A `writer` argument is accepted for
Dream Bucket compatibility (`writer.append("episodes", record)`).

## CLI

```bash
python -m tools.episode_annotation_tool annotate --phase expl --summary "read thermodynamics_general cartridge" --session-id session_1
python -m tools.episode_annotation_tool read
```

JSON to stdout, summary to stderr. Exit 0 = logged/ok, 1 = error (invalid
input), 2 = IO failure. Pure stdlib; same `PYTHONPATH= ` prefix rule in the
Kitbash `.venv`.

**Spec:** `SPEC-episode_annotation_tool_v1.md` · **Test:** `TEST-episode_annotation_tool_examples.json`
