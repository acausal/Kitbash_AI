# inverted_index_builder

Token→document inverted index with TF/DF + IDF (Historical AI batch). Stateless,
deterministic, stdlib-only. See SPEC-inverted_index_builder_v1.md and the shared
Historical AI contract.

## Library

```python
from tools.inverted_index_builder import build_index, compute_idf, add_document, merge_indexes
r = build_index([{"id":"d1","tokens":["ai","ml","ai"]},{"id":"d2","tokens":["ml","nlp"]}], {})
#   r["index"]: {token: {document_frequency, postings:[{doc_id, term_frequency}]}}
#   r["idf_values"]: {token: idf}
r2 = add_document(r, {"id":"d3","tokens":["ai","nlp"]})   # returns a NEW index
merged = merge_indexes([r, r2])
idf = compute_idf({"ai":2,"ml":2}, total_documents=3, idf_scheme="standard")
```

IDF scheme: `standard` (smoothed ln), `log`, `probabilistic` (BM25-style).

## CLI

```bash
echo '{"corpus":[...]}' | python -m tools.inverted_index_builder
python -m tools.inverted_index_builder --idf --input dfmap.json --output idf.json
python -m tools.inverted_index_builder --add --input add.json
python -m tools.inverted_index_builder --merge --input indexes.json
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Notes
- All functions are pure: `add_document`/`merge_indexes` return new dicts.
- `run_id`/`timestamp` differ per call; index content is fully deterministic.
