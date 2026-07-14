# trie

Prefix-tree (trie) for fast prefix lookups, autocomplete, and negation-aware
search. Nested-dict implementation, no external deps (`json`, `collections`).
Useful for command completion, query routing, grain-name lookup, fast
negation-pattern detection.

## Functions

| Function | Purpose |
|----------|---------|
| `build_trie(vocabulary, case_sensitive=True)` | Build nested-dict trie |
| `search_trie(trie, query, case_sensitive=True)` | Exact-match lookup |
| `prefix_search(trie, prefix, case_sensitive=True, max_results=None)` | All terms with prefix |
| `suggest_completions(trie, prefix, case_sensitive=True, max_suggestions=10)` | Autocomplete |
| `negation_search(trie, patterns, case_sensitive=True, max_results=None)` | Exclude-by-prefix |
| `get_trie_stats(trie)` | Node/depth/branch statistics |
| `serialize_trie(trie)` / `deserialize_trie(json_str)` | JSON persistence |

Trie is JSON-serializable (nested dicts; terminal nodes carry the END marker).
All query functions operate on the nested dict directly.

## Errors

- `ValueError` (exit 1): empty vocabulary/query/prefix, non-strings, empty strings, invalid patterns, invalid JSON.
- `RuntimeError` (exit 2): file I/O or parse failure.

## Usage

```bash
python -m tools.trie build --vocabulary vocab.jsonl --case-sensitive --output trie.json
python -m tools.trie search --trie trie.json --query photosynthesis
python -m tools.trie prefix-search --trie trie.json --prefix photo
python -m tools.trie suggest --trie trie.json --input pho --max-suggestions 5
python -m tools.trie negation-search --trie trie.json --exclude-patterns '["photo","atp"]'
python -m tools.trie stats --trie trie.json
```

Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-trie_v1.md` · **Test:** `TEST-trie_examples.json`

> **Deviation note:** the TEST's `node_count_max: 50` for the 6-word canonical
> vocabulary is mathematically impossible — those words span 70 characters, so
> the trie has ~61 nodes. The committed TEST bound was corrected to `70`
> (min unchanged at 30). All other TEST bounds pass against correct trie math.
