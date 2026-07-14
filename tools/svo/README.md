# svo

Subject-Verb-Object extraction (v1). Part of the input-sieve / document-
preprocessing pipeline: pulls (subject, verb, object) triples from spaCy's
dependency parse, complementing NER (entities) and negation_detector (modifiers).
Isolation-first tool — stdlib + spaCy + optional `structured_logger` only.

v1 extracts one SVO per main clause, using the sentence ROOT as the verb and
head-word subject/object (nsubj/nsubjpass for subject; dobj/iobj/attr for
object; passive object surfaces as subject via nsubjpass). Sentences without a
main verb are skipped. Nested clauses, full-span phrases, and SRL are v2+.

## Library

```python
from tools.svo import extract_svo, SVO

svos = extract_svo("The CEO announced a new product.")
# [SVO(subject="The CEO", verb="announced", obj="product", ...)]
```

`extract_svo(text) -> List[SVO]`

- Empty string returns `[]` (not an error); `None`/non-str raises `ValueError`.
- `subject`/`obj` are the dependency head token's text; `None` when absent.
- `verb` is the sentence ROOT. Each SVO carries char offsets + full `sentence`.
- Missing spaCy model raises `RuntimeError` with the install command.

## CLI

```bash
python -m tools.svo input.txt
python -m tools.svo input.txt --output triples.json
python -m tools.svo input.txt -o triples.json
```

Writes JSON `{svos, svo_count, with_subject, with_object}` to `--output` (or
stdout) and a summary line to stderr. Exit 0 on success, 1 on failure.

## Requirements

- `spacy` + `en_core_web_sm` (shared with tokenizer/negation_detector/ner).
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.svo ...`
