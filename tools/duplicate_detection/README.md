# duplicate_detection

Duplicate detection over a token corpus (Historical AI batch). Four deterministic
strategies, stdlib-only, stateless, JSON I/O. See `SPEC-duplicate_detection_v1.md`.

## Library

```python
from tools.duplicate_detection import detect_duplicates
corpus = [
  {"id":"d1","tokens":["the","cat","sat"]},
  {"id":"d2","tokens":["cat","sat","the"]},   # same multiset -> exact dup
  {"id":"d3","tokens":["dog","ran"]},
]
res = detect_duplicates(corpus, strategy="exact", threshold=1.0, keep_strategy="first")
```

Strategies:
- `exact` — sorted token multiset key; O(N log N) sort + O(N) group.
- `jaccard` — pairwise Jaccard over token sets; pair dup if ≥ `threshold`. O(N²).
- `shingle` — k-shingle sets (k=`shingle_size`, default 3); pair dup by shingle-Jaccard ≥ `threshold`. O(N²·k).
- `minhash` — MinHash signatures (h=`minhash_hashes`, default 64); pair dup by signature-similarity ≥ `threshold`. O(N·h).

`keep_strategy` picks the group representative: `first` (input order) / `shortest` / `longest`
(by token count). Groups are transitive (union-find over threshold-passing pairs).

Error modes (→ stderr JSON, exit 1): empty corpus, unknown strategy, threshold not in [0,1], unknown keep_strategy. `jaccard`/`shingle`/`minhash` are O(N²) pairwise — large corpora are memory/CPU heavy (documented, not specially handled).

## CLI

```bash
echo '{"corpus":[...]}' | python -m tools.duplicate_detection --strategy jaccard --threshold 0.5
python -m tools.duplicate_detection --input corpus.json --output dups.json --strategy minhash
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Post-1.0

This tool will be registered with `ToolRegistry` (see `SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md`)
for grain-system deduplication. For now, invoked directly by tests or the sleep pipeline.
