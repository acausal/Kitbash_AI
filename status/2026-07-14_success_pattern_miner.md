# 2026-07-14 — tools/success_pattern_miner built + verified

Scope: implement SPEC-success_pattern_miner_v1.md (the next tool from the
ready-for-spec queue). No core Kitbash socket changes — `tools/` is isolated.

## Built (9 files, tools/success_pattern_miner/)
- `__init__.py`, `__main__.py`, `miner_schema.py` (Pattern/RunResult dataclasses)
- `pattern_extraction.py` (ngrams, length 2–6 sliding windows)
- `filtering.py` (is_success + filter_success_traces w/ time window)
- `core.py` (mine_success_tool_sequences / mine_success_grain_patterns /
  mine_mixed_success_patterns; support/coverage/confidence math per SPEC)
- `cli.py` (--pattern-type sequences|grains|mixed; JSON array OR JSONL input;
  stdin/--input, stdout/--output; exit 0/1/2)
- `README.md`, `TEST-success_pattern_miner_examples.json` (8 SPEC test cases)

## Verification (ad-hoc, executed — NOT suite-green)
Temp verifier under `%TEMP%/hermes-verify-success_pattern_miner.py`, 13/13 PASS:
- 8 fixture cases (tool seq, grain pattern, mixed, failure-drop, low-freq filter,
  error_signal-success, empty input, missing-field ValueError)
- real `python -m tools.success_pattern_miner` runs: sequences (JSONL file,
  min-frequency 2 -> 3 success traces, patterns present) and grains (type correct)
Temp verifier deleted post-run.

## Honest notes / deviations
- The SPEC's `mine_mixed_success_patterns` interleaves tool+grain by pairing the
  top-ranked tool pattern with the corresponding grain pattern at the same rank
  (zip), keeping `frequency` = min of the two so a mixed pattern requires BOTH
  the tool sequence AND the grain pattern to recur >= min_frequency. This is a
  reasonable reading of "interleave"; if you want paired-by-trace co-occurrence
  instead, that's a different (heavier) extraction — flag it.
- SPEC error semantics say "empty pattern output -> fail loud"; I chose to return
  an empty patterns array (exit 0) for empty/zero-pattern runs, matching the
  SPEC Testing Strategy case 6 ("0 traces -> empty patterns array, no error") and
  the fail-loud rule applying only to malformed input/missing fields. Consistent.
- Divergence from sequence_pattern_miner: that tool consumes log_parser's
  `chain` of {element_type,element_id} dicts; this tool uses SPEC-success's own
  simpler schema (sequence/grain_activations lists). Documented in README.

## Committed + pushed
- Commit: all 9 tool files + this status record.
- Pushed to origin/main (GCM-cached token).
