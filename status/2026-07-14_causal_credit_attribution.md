# 2026-07-14 — tools/causal_credit_attribution built + verified

Scope: implement SPEC-causal_credit_attribution_v1.md (last ready-for-spec tool;
attribution of success credit to trace components). No core Kitbash socket
changes — `tools/` is isolated.

User framing: built now so the CWL episode-dependency brief's custom fields
(work_type / depends_on_results) can be consumed RETROACTIVELY later. The tool
already accepts `tool_metadata` to drive input_output_salience — no future code
change needed when those fields arrive.

## Built (8 files, tools/causal_credit_attribution/)
- `__init__.py`, `__main__.py`, `attribution_schema.py`
- `attribution_signals.py` (positional, historical_correlation, pattern_membership,
  input_output_salience — base 0.5, elevated by tool_metadata work_type/depends_on_results)
- `heuristic_aggregation.py` (weighted credit + normalize to sum 1.0)
- `core.py` (attribute_credit_to_tools / attribute_credit_to_grains /
  batch_attribute_credit; confidence flag; positional-only fallback)
- `cli.py` (--trace/--traces/--patterns/--historical/--tool-metadata/--batch/--grain/
  --weights-*; exit 0/1/2)
- `README.md`, `TEST-causal_credit_attribution_examples.json` (7 SPEC cases)

## Honest deviations / fixes found during verification
1. **SPEC positional formula typo.** SPEC writes `(N - i) / N` but its prose and
   worked example both say later tools get higher (last=1.0). Implemented
   `(i+1)/N` (later=higher) and flagged in code + README. No ambiguity in intent.
2. **Real tool bug fixed:** `attribute_credit_to_grains` referenced `success_patterns`
   (undefined in its arg list) — would crash on any pattern-aware grain attribution.
   Added optional `success_patterns` param (grain pattern-membership needs it).
   SPEC's grain signature omits it; extension is required for correctness.
3. **Fixtures** corrected: tokenizer historical success rate is 0.6667 (2/3), not
   0.67; verifier placeholder expansion fixed (dict samples wrapped, list samples not).

## Verification (ad-hoc, executed — NOT suite-green)
Temp verifier under %TEMP%/hermes-verify-causal_credit_attribution.py: 10/10 PASS
(simple chain positions, pattern membership, historical correlation 0.6667, weak
link lower, batch, grain attribution, positional-only confidence=low) + real CLI
run (single trace -> exit 0, total=1.0, n=4). Temp verifier deleted post-run.

## Committed + pushed
Pushed to origin/main (GCM-cached token). 9 files: 8 tool + TEST fixture + this
status record.

## Ready-for-spec queue — now EMPTY (all implemented)
- success_pattern_miner v1 ✅ (earlier this session)
- positive_signal_scorer v1 ✅
- causal_credit_attribution v1 ✅
- (BRIEF-CWL_EPISODE_DEPENDENCY_INTEGRATION remains a design brief, not a code SPEC)
