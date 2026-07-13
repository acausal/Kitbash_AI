# ner

Named Entity Recognition (v1). Part of the input-sieve / document-preprocessing
pipeline: extracts named entities (PERSON, ORG, GPE, DATE, MONEY, ...) from text
using spaCy's pre-trained NER model. Isolation-first tool — stdlib + spaCy +
optional `structured_logger` only.

v1 uses spaCy's default entity types with optional label filtering. Fine-tuning,
custom types, entity linking, relationships, and confidence scores are deferred
to v2+ (see `SPEC-ner_v1.md`).

## Library

```python
from tools.ner import extract_entities, Entity

ents = extract_entities("Apple CEO Tim Cook announced a product.")
ents = extract_entities(text, labels=["PERSON", "ORG"])   # filter by type
```

`extract_entities(text, labels=None) -> List[Entity]`

- Empty string returns `[]` (not an error); `None`/non-str raises `ValueError`.
- Unknown label in `labels` raises `ValueError` (with the valid set).
- Missing spaCy model raises `RuntimeError` with the install command.
- `Entity` fields: `text, label, start, end, doc_idx`.
- Under label filtering, `doc_idx` preserves the original document entity index
  (may be non-contiguous) so ordering matches the source.

## CLI

```bash
python -m tools.ner input.txt
python -m tools.ner input.txt --labels PERSON,ORG
python -m tools.ner input.txt -l PERSON,ORG,GPE
python -m tools.ner input.txt --output entities.json
```

Writes JSON `{entities, entity_count, label_counts}` to `--output` (or stdout)
and a summary line to stderr. Exit 0 on success, 1 on failure.

## Requirements

- `spacy` + `en_core_web_sm` (shared with `tokenizer` / `negation_detector`).
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.ner ...`
