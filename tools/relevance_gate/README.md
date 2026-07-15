# tools.relevance_gate

Deterministic, query-time relevance filter for retrieved candidate facts. Given a
query, Mamba context, and a set of candidate facts (from CARTRIDGE / GRAIN), it
scores each candidate's relevance and decides which survive into the generation
LLM's prompt — using **zero models**. Composes already-built `tools/` packages.

**This is NOT:** MTR's salience gate (different layer/job), an `InferenceEngine`
(doesn't compete for a confidence threshold; always feeds forward), or a relevance
model (no BitNet/LLM call). See `docs/SPEC-relevance_gate_v1.md`.

## API
- `score_candidates(query, context, candidates, weights=None) -> List[dict]`
- `is_ambiguous(scored, margin_threshold=0.15, volume_threshold=8) -> bool`
- `apply_relevance_gate(query, context, candidates, weights=None, top_k=None) -> dict`

## Dimensions (composite-weighted)
| Dimension | Weight | Source |
|---|---|---|
| `lexical` (BM25) | 0.35 | `tfidf_ranker` |
| `similarity_bucket` | 0.25 | `cosine_similarity` over TF-IDF vectors → `interpret()` |
| `entity_overlap` | 0.20 | `ner` (Jaccard of entity texts) |
| `structural_overlap` | 0.20 | `svo` (partial-match Jaccard of triples) |

`negation_flag` is computed (polarity mismatch) but **excluded** from the composite
score (metadata for the generator). Weights are configurable.

## Ambiguity trigger
The gate only fires when retrieval is ambiguous:
- **margin**: top-2 relevance scores within `margin_threshold`, OR
- **volume**: more than `volume_threshold` candidates.

Otherwise it is a documented no-op pass-through (`gate_fired=false`).

## Dependencies
`duplicate_detection`, `tfidf_ranker`, `cosine_similarity`, `ner`, `svo`,
`negation_detector` (all in `tools/`). `ner`/`svo`/`negation_detector` load
spaCy (`en_core_web_sm`); **run under `.venv`** (the system's reliable interpreter —
bare `python` lacks spaCy). If spaCy is unavailable the tool raises `RuntimeError`
(fail-loud, not silent).

## Testing
`TEST-relevance_gate_examples.json` via `tools/run_TEST.py`. **Run it with the
`PYTHONPATH= ` prefix** so the Hermes-leaked pydantic-core doesn't shadow the
Kitbash venv's (without it, spaCy raises `pydantic_core._pydantic_core`
and the gate/spaCy-dependent tools fail to load):
```
PYTHONPATH= .venv/Scripts/python.exe tools/run_TEST.py
```
(Minimum cases: clear winner pass-through, close-margin fires, volume overflow
fires, duplicate collapse, negation flagged, malformed candidate -> ValueError.)
