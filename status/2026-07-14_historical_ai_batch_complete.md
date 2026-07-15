# Status — Historical AI Batch (6 tools) complete

**Date:** 2026-07-14
**Scope:** Build the 6 spec-only retrieval/IR/stats tools from `SPEC-historical_ai_shared_contract_v1.md`, all confined to `tools/`. No core-pipeline or `SOCKET_MAP.md` changes.
**Status:** DONE. All 6 tools built, verified, committed, pushed. Standing green: **70 PASS / 0 FAIL** via `tools/run_TEST.py`.

## What shipped

| # | Tool | Core functions | Verified cases | Commit |
|---|------|---------------|----------------|--------|
| 1 | `frequency_analysis` | `analyze_frequencies`, `analyze_corpus_frequencies`, `compute_coverage`, `frequency_histogram` | 40 → +6 | `fe3421b` |
| 2 | `inverted_index_builder` | `build_index`, `compute_idf`, `add_document`, `merge_indexes`, `index_ops` | 45 → +5 | `ab7e3ae` |
| 3 | `boolean_search` | `search`, `parse_query`, `execute_query` (recursive-descent engine) | 52 → +7 | `dd03be6` |
| 4 | `tfidf_ranker` | `compute_tfidf`, `rank_documents` (std/sublinear/bm25), `cosine_similarity`, `bm25_score`, `scoring` | 59 → +7 | `52e3494` |
| 5 | `markov_chain` | `build_chain`, `compute_entropy`, `generate_sequence` (seeded), `next_token_distribution`, `generation` | 65 → +6 | `1ddce81` |
| 6 | `naive_bayes_classifier` | `train_classifier` (Bernoulli/Multinomial+Laplace), `classify`, `batch_classify`, `evaluate_classifier` (P/R/F1, macro_f1) | 70 → +5 | `56799f6` |

Plus:
- `tools/historical_common.py` — shared helper (config normalize, stopwords, envelope, CLI/error). Imported as `from tools.historical_common import ...`.
- `tools/run_TEST.py` — durable runner; `OWNED_PACKAGES` now = {success_pattern_miner, positive_signal_scorer, causal_credit_attribution, templating, frequency_analysis, inverted_index_builder, boolean_search, tfidf_ranker, markov_chain, naive_bayes_classifier}. Scans `TEST-*.json`, executes owned `test_cases`, SKIPs legacy/heterogeneous fixtures. Exit non-zero on FAIL.

## Bugs caught + fixed during the build (real, not inferred)
- `frequency_analysis`: `load_input` needed `json.loads` not `json.load` on stdin; `compute_coverage` reused `cum` after reset (coverage_achieved=0); `analyze_frequencies` `top_tokens` indexed a tuple as a dict; `add_document` alias `index_state→index`.
- `boolean_search` / `tfidf_ranker`: `_check_expected` lost the `frequency_analysis` guard twice (restored); `cosine_similarity` returns a bare float → runner's `_check_expected` needed a scalar-result guard; alias `vector_a/vector_b → vec_a/vec_b`.
- `markov_chain`: `deterministic` check was broken (`_last_kwargs` nonexistent) → moved real re-run comparison into `main()`; fixture `gen_len:4` corrected to 2 (generation genuinely dead-ends at 2 tokens from `["ai"]`).
- `naive_bayes_classifier`: `evaluate_classifier` puts `test_documents` at result top-level → runner check read wrong location.

## Verification evidence (executed this session)
```
python tools/run_TEST.py
70 PASS / 0 FAIL across 70 executed cases (14 fixtures skipped)
EXIT=0
```
Each tool was also smoke-tested via `python -m tools.<pkg>` (CLI stdin→stdout, exit 0). Examples: inverted_index_builder top-doc ranked first; markov_chain deterministic generation; naive_bayes train @100% acc + classify conf 0.99.

## Honesty notes
- "Done" = every tool has an executed, passing TEST fixture under `tools/run_TEST.py` (70/0) and a committed, pushed SHA. The helper (`historical_common.py`) is exercised indirectly by all 6 tools but has no standalone fixture.
- No credentials/keys/tokens appeared in any turn.
- Per-turn guardrail "unverified" re-flag loop: mitigated by the durable runner; each turn re-ran `python tools/run_TEST.py` via a fresh temp gate and deleted it (no `hermes-verify-*` left in Temp).
- `SOCKET_MAP.md` and core pipeline: unchanged (out of scope; tools/ isolation respected).

## Out of scope / not done
- Integration of these tools into the core query/sleep pipeline (post-1.0, per the Isolation Contract).
- Normalizing the pre-existing legacy/heterogeneous TEST fixtures into `OWNED_PACKAGES` (they SKIP, not FAIL).
