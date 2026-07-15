# SPEC: Duplicate Detection v1

> Implemented 2026-07-14 in `tools/duplicate_detection/`. Stdlib-only, stateless,
> deterministic, JSON I/O. Confirms to the Historical AI shared contract
> (envelope + shared config + CLI `tools/historical_common`).

## Status
Implemented.

## Strategies (four)
- **exact** — normalized token multiset (sorted tuple) as key; O(N log N) sort + O(N) group.
- **jaccard** — pairwise Jaccard over token sets; pair dup if `jaccard ≥ threshold`. O(N²).
- **shingle** — k-shingle sets (k=`shingle_size`, default 3); pair dup by shingle-Jaccard ≥ `threshold`. O(N²·k).
- **minhash** — MinHash signatures (h=`minhash_hashes`, default 64) via seeded MD5; pair dup by signature-similarity ≥ `threshold`. O(N·h).

## Config
`threshold` ∈ [0,1], `keep_strategy` ∈ {first, shortest, longest}, case sensitivity
(`lowercase`), tokenization (`remove_stopwords`, `stopword_list`, `min_token_length`).
Defaults from `tools/historical_common.normalize_config`.

## Error modes
- empty corpus → `ValueError` → exit 1
- invalid strategy → `ValueError` → exit 1
- threshold out of [0,1] → `ValueError` → exit 1
- memory exhaustion → documented risk for O(N²) strategies; not specially handled (no streaming).

## Related
Tokenizer (upstream — not used here; this tool tokenizes inline via `historical_common`
to stay stdlib-only like the rest of the batch), Deduplication pipeline, Frequency Analysis.

## Non-goals / deferred
No visualization, ML, streaming, or custom formats beyond JSON. Registry/manifest
integration (sieve_hooks) deferred to post-1.0 (`SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`).
