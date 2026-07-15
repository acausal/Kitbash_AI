# tfidf_ranker

TF-IDF scoring + cosine (or BM25) ranking over a tokenized corpus (Historical AI
batch). Stateless, deterministic, stdlib-only. See SPEC-tfidf_ranker_v1.md.

## Library

```python
from tools.tfidf_ranker import rank_documents, compute_tfidf, cosine_similarity, bm25_score
r = rank_documents(["ai","ml"], [{"id":"d1","tokens":["ai","ml","nlp"]},{"id":"d2","tokens":["cv"]}], {"tfidf_variant":"standard"})
#   r["ranking"]: docs by score desc (cosine over standard TF-IDF vectors)
r2 = rank_documents(["ai","ml"], corpus, {"tfidf_variant":"bm25"})   # BM25 scoring
vecs = compute_tfidf(corpus, {"tfidf_variant":"sublinear"})
sim = cosine_similarity(vecs["document_vectors"]["d1"], vecs["document_vectors"]["d2"])
```

TF variants: `standard` (raw tf), `sublinear` (1+ln tf), `bm25` (saturation).

## CLI

```bash
echo '{"query":"ai ml","corpus":[...]}' | python -m tools.tfidf_ranker
python -m tools.tfidf_ranker --tfidf-variant bm25 --query "ai ml" --input corpus.json
python -m tools.tfidf_ranker --tfidf --input corpus.json
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Notes
- `rank_documents` query is a token list (string split on whitespace unless already a list).
- Scores are deterministic; `rank_documents` ties broken by doc_id.
- `run_id`/`timestamp` differ per call; vectors are fully deterministic.
