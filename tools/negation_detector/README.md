# negation_detector

Detect negation in text and mark nearby tokens (v1). Part of the input-sieve /
document-preprocessing pipeline: finds negation markers (`not`, `no`, `never`,
`neither`, `nor`, and split contractions via lemma `not`) and flags every token
within a distance `window` of a marker as `is_negated`. Isolation-first tool —
stdlib + spaCy + optional `structured_logger` only.

v1 uses a hardcoded marker list + fixed window. Linguistic scope analysis,
multi-word negations ("in no way"), and double-negative logic are deferred to
v2+ (see `SPEC-negation_detector_v1.md`).

## Library

```python
from tools.negation_detector import detect_negations, Token

tokens = detect_negations("I don't like this")          # window=5 default
tokens = detect_negations("I don't like this", window=2)
negated = [t.text for t in tokens if t.is_negated]
```

`detect_negations(text, window=5) -> List[Token]`

- Empty string returns `[]` (not an error); `None`/non-str raises `ValueError`.
- `window` must be a positive int (`0`, negative, or bool raises `ValueError`).
- Markers are included in their own window, so they are marked negated too.
- `Token` fields: tokenizer's set plus `is_negated`.

Note: spaCy splits contractions ("don't" → ["do", "n't"]); the "n't" token has
lemma "not" and is matched as a marker — so only base markers need listing.

## CLI

```bash
python -m tools.negation_detector input.txt
python -m tools.negation_detector input.txt --window 3
python -m tools.negation_detector input.txt -w 3
```

Prints JSON `{tokens, token_count, negated_count, negation_markers}` to stdout
and a summary line to stderr. Exit 0 on success, 1 on failure.

## Requirements

- `spacy` + `en_core_web_sm` (shared with `tokenizer`).
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.negation_detector ...`
