# status/ — repo-local Kitbash work record

Git-tracked, Kitbash-scoped log of work done in this repo. Every entry here is
versioned with the code it describes and synced to `origin/main` on each push,
so the "what changed and why" record for Kitbash travels with the source.

## Why this dir exists separately from session_log.md
- `session_log.md` (agent-sandbox root, **outside this repo**) is the broad,
  cross-project agent activity ledger. It may include work unrelated to Kitbash,
  so it is deliberately kept OUT of the repo.
- `status/` is the Kitbash-only subset: work that belongs with the code and
  should be versioned and pushed. The two are complementary, not redundant.
- Nothing here should ever pull non-Kitbash content into the repo.

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
- Cross-project / non-Kitbash activity — that stays in `session_log.md`.
- Raw session transcripts, secrets, or local-only config.
