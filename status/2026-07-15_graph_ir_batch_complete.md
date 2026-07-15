# Status — Graph / IR Batch (3 tools) complete

**Date:** 2026-07-15
**Scope:** Build the 3 spec-only graph / deduplication tools (Duplicate Detection, Hypergraph Traversal, Topological Statistics) from the 3 provided SPECs, confined to `tools/`. No core-pipeline or `SOCKET_MAP.md` changes.
**Status:** DONE. All 3 tools built, verified, committed, pushed. Standing green: **92 PASS / 0 FAIL** via `tools/run_TEST.py`.

## Locked decisions (from checkpoint)
- **CLI:** `--output` convention (not `--output-json`); the JSON part is implicit. SPEC docstrings updated to say `--output`.
- **Registry/sieve_hooks manifests:** deferred to post-1.0. No manifest files; each tool README notes post-1.0 registration with `ToolRegistry` (`SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`).
- **Graph defaults:** undirected default (`--directed` opt-in); weighted w/ 1.0 fallback (`--unweighted`); cycles allowed; `find_paths` / shortest-path metrics return simple paths / hop-based lengths (deterministic, O(N·E) bound); batch only.

## What shipped

| # | Tool | Core functions | Verified cases | Commit |
|---|------|---------------|----------------|--------|
| 1 | `duplicate_detection` | `detect_duplicates` (exact / jaccard / shingle / minhash), union-find grouping, `keep_strategy` | 77 → +7 | `2481b1d` |
| 2 | `hypergraph_traversal` | `find_neighbors`, `find_paths`, `reachability_analysis`, `hyperedge_coverage` | 84 → +7 | `9f8424e` |
| 3 | `topological_statistics` | `compute_degree_stats`, `compute_clustering_coefficients`, `compute_path_lengths`, `compute_centrality` (degree/closeness/betweenness/eigenvector), `analyze_components` | 92 → +8 | `c6707d9` |

Plus: `run_TEST.py` now owns all 13 packages (prior 10 + these 3). Each tool = 8 files + SPEC doc; fixtures generated via the tool itself.

## Bugs caught + fixed during the build (real, not inferred)
- **duplicate_detection:** the runner reads `raises` from inside `expected_output`; my negative TEST cases placed `raises` at the top level → fixed (7/7 pass).
- **topological_statistics:** clustering-coefficient denominator was `k*(k-1)` → should be `k*(k-1)/2` (triangle CC now 1.0, was 0.5). Caught by fixture `clustering_triangle` expecting 1.0. Also corrected fixture `mean_degree` 2.0→1.6 (sample graph has an isolated node).

## Verification evidence (executed this session)
```
python tools/run_TEST.py
92 PASS / 0 FAIL across 92 executed cases (14 fixtures skipped)
EXIT=0
```
Each tool was also smoke-tested via `python -m tools.<pkg>` (CLI stdin→stdout, exit 0). Examples: duplicate_detection grouped d1/d2 as exact dups; hypergraph_traversal returned 3 simple paths A→D + coverage {e1,e3}; topological_statistics most_central_by_degree=A, 2 components w/ isolated I.

## Docs updated this round (this commit)
- `tools/README.md`: added "Graph / IR Batch (2026-07-14→2026-07-15)" subsection (3 tools + locked graph defaults); runner count 70→92 PASS.
- `README.md`: "## Tools" note now lists both batches (9 tools total); date 2026-07-14→2026-07-15.
- This `status/` note.

## Honesty notes
- "Done" = every tool has an executed, passing TEST fixture under `tools/run_TEST.py` (92/0) and a committed, pushed SHA. `historical_common.py` is exercised indirectly by all tools (no standalone fixture).
- No credentials/keys/tokens in any turn.
- The per-turn guardrail "unverified" re-flag loop: mitigated by the durable runner; each turn re-ran `python tools/run_TEST.py` via a fresh temp gate and deleted it.
- `SOCKET_MAP.md` and core pipeline: unchanged (out of scope; tools/ isolation respected).

## Out of scope / not done
- Tool-registry / sieve_hooks manifest wiring (post-1.0, per `SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`).
- Weighted shortest-path metrics in topological_statistics (path metrics are hop-based by design).
- Integration into Sleep Stages 2/3 (deferred with the rest of the tools/ sandbox).
