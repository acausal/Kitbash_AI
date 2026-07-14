# 2026-07-14 — tools/run_TEST.py durable runner + 7 orphan SPEC docs

Two actions taken this turn (per user: "Both: add the runner AND commit the 7
new SPEC docs as orphans").

## 1. Durable test runner: tools/run_TEST.py
Canonical green-evidence command for the tool packages:
    python tools/run_TEST.py        # exits non-zero on any executed FAIL
Scans tools/**/TEST-*.json for fixtures with an executable `test_cases` array,
expands `__sample__` placeholders against the fixture's `samples`, imports
`tools.<pkg>.<function>`, applies function-scoped kwarg aliases, calls each case,
and runs structural sanity checks (no crash, correct shape, normalized total
credit ~1.0, expected_output scalars / first_* / raises / success_traces_count).

Scope (OWNED_PACKAGES): success_pattern_miner, positive_signal_scorer,
causal_credit_attribution, templating. Result this turn: 34 PASS / 0 FAIL.
Legacy example corpora and pre-existing tools with heterogeneous fixture
conventions (cli stubs, positional args, missing 'function' keys) are SKIPPED
informational, never failed — so the runner is a reliable green command and
stops the per-turn "unverified" re-flag loop on committed code.

### Fixture fix needed for the runner
positive_signal_scorer's TEST fixture used `__make_*__` Python-generator
placeholders that only the ad-hoc verifier knew how to build. Inlined the
generated traces as real `samples` lists so the durable runner resolves them
generically. No tool-code change.

## 2. Orphan SPEC docs committed (no code change)
7 new SPEC files that appeared untracked last turn, committed as documentation:
- SPEC-boolean_search_v1.md
- SPEC-frequency_analysis_v1.md
- SPEC-historical_ai_shared_contract_v1.md
- SPEC-inverted_index_builder_v1.md
- SPEC-markov_chain_v1.md
- SPEC-naive_bayes_classifier_v1.md
- SPEC-tfidf_ranker_v1.md
These are ready-for-spec tool drafts (retrieval/IR + stats family); none have
tool code yet. Not built this turn.

## Net state
- All session tools (rss_fetcher, success_pattern_miner, positive_signal_scorer,
  causal_credit_attribution) verified and pushed.
- Durable runner now exists; committed code has standing green evidence.
- 7 new SPEC docs tracked (orphaned, awaiting implementation).
