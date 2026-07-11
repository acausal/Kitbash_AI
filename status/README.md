# status/ — repo-local work record

Canonical, git-tracked log of Kitbash_AI work. Every entry here is versioned
with the code it describes and synced to `origin/main` on each push, so the
"what changed and why" record travels with the source instead of living only
in the agent-sandbox root (`session_log.md`, which is outside the repo and not
synced).

## What belongs here
- One dated file per work session/turn: `YYYY-MM-DD.md` (or
  `YYYY-MM-DD_<slug>.md` if more than one entry per day).
- Each file: what was decided, what changed (files + commit), how it was
  verified, caveats, and what was deliberately NOT done.

## Format
Terse, additive, honest. Mirror the discipline in `STATUS_2026-07-10.md` and
`SOCKET_MAP.md`:
- Cite the actual socket/cell state, don't round up.
- "Verified" means executed output, not inference. Mark ad-hoc checks as
  ad-hoc, not suite-green.
- Flag caveats and deferred items explicitly.

## What does NOT belong here
- `STATUS_2026-07-10.md` / `SOCKET_MAP.md` remain the socket-level "is it done?"
  map (separate files, updated in place). This `status/` dir is the chronological
  work log that references them.
- Raw session transcripts, secrets, or local-only config.

## Legacy
`../session_log.md` (agent-sandbox root, outside repo) is the prior external
activity log. New work goes here; `session_log.md` is retained for the morning
brief's overnight pull but is no longer the canonical record.
