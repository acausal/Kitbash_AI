# tokenizer

Generic spaCy-based text tokenization (v1, English). Part of the input-sieve /
document-preprocessing pipeline: turns raw text (user queries or extracted
document text) into clean `Token` sequences with POS, lemma, and stop/punct/space
flags. Isolation-first tool — stdlib + spaCy + optional `structured_logger` only.

v1 is English-only (`en_core_web_sm`); slang/abbreviation/spelling/multi-language
normalization are deferred to v2+ (see `SPEC-tokenizer_v1.md`).

## Library

```python
from tools.tokenizer import tokenize, Token

tokens = tokenize("What is machine learning?")
tokens = tokenize("running fast", lemmatize=True)          # lemma="run"
tokens = tokenize("What is X?", remove_stop=True)          # drops "What", "is"
```

`tokenize(text, lemmatize=False, remove_stop=False, model="en_core_web_sm") -> List[Token]`

- Empty string returns `[]` (not an error); `None`/non-str raises `ValueError`.
- Missing spaCy model raises `RuntimeError` with the install command.
- `Token` fields: `text, lemma, pos, is_stop, is_punct, is_space, idx, doc_idx`.

## CLI

```bash
python -m tools.tokenizer input.txt
python -m tools.tokenizer input.txt --lemma --remove-stop
python -m tools.tokenizer input.txt -l -s
```

Prints a JSON object `{tokens, token_count, stop_word_count}` to stdout and a
summary line to stderr. Exit 0 on success, 1 on failure.

## Requirements

- `spacy` + `en_core_web_sm` (`python -m spacy download en_core_web_sm`).
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.tokenizer ...`
