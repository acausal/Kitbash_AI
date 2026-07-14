# 2026-07-14 — Orphan SPEC/BRIEF docs committed (cleanup)

Scope: recover the 11 untracked `tools/` SPEC/BRIEF docs that prior sessions
authored alongside their tools but forgot to `git add`. No code change — docs
only. User-directed bulk commit (option 2 of the recovery offer).

## Files committed (11)
Shipped-tool SPEC docs (tool dir already exists + committed):
- `SPEC-diff_patch_v1.md`        -> `diff_patch/`
- `SPEC-edge_weight_mutation_v1.md` -> `edge_weight_mutation/`
- `SPEC-episode_annotation_tool_v1.md` -> `episode_annotation_tool/`
- `SPEC-math_evaluation_v1.md`   -> `math_evaluation/`
- `SPEC-templating_v1.md`        -> `templating/`
- `SPEC-timeseries_windowed_operations_v1.md` -> `timeseries_windowed_operations/`
- `SPEC-unit_conversion_v1.md`   -> `unit_conversion/`

Pure design artifacts (no tool dir yet):
- `BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION.md` (cross-tool integration brief)
- `SPEC-causal_credit_attribution_v1.md` (spec only)
- `SPEC-positive_signal_scorer_v1.md` (spec only)
- `SPEC-success_pattern_miner_v1.md` (spec only; note `sequence_pattern_miner/`
  exists but not `success_pattern_miner/`)
