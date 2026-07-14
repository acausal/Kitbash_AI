# contractions

Deterministic English contraction expansion for preprocessing (runs before
`tokenizer` / `negation_detector`; "don't know" → "do not know" widens the
negation window). Wraps the `contractions` PyPI library (v0.1.73); `fix()` does
the substitution and preserves case. Pure deterministic — no neural nets.

## Library

```python
from tools.contractions import expand_contractions, expand_word, list_contractions

# full text
expand_contractions("I don't think I'll go. That's fine.")
# -> {expanded_text: "I do not think I will go. That is fine.",
#     contractions_found: 3,
#     contractions_list: [{contraction:"don't", expansion:"do not", position:2}, ...]}

# single word
expand_word("don't")   # {is_contraction: True,  expanded: "do not"}
expand_word("hello")  # {is_contraction: False, expanded: "hello"}

# reference dictionary (791 entries in v0.1.73)
list_contractions()   # {total_contractions: 791, contractions: {...}}
```

- `expand_contractions(text, preserve_case=True)` → dict with `expanded_text`,
  `contractions_found`, and `contractions_list` (each with `contraction`,
  `expansion`, `position` = 1-based word index).
- `expand_word(word, preserve_case=True)` → dict with `is_contraction`,
  `expanded`, `case_preserved`.
- `list_contractions()` → full merged dictionary.

### Case preservation
Honors the library: `don't`→`do not`, `Don't`→`Do not`, `DON'T`→`DO NOT`.
`--preserve_case false` still uppercases a leading capital when the input did.

### Possessives
The library does **not** expand possessives ("John's" stays "John's"). This
tool follows the library's actual behavior (the SPEC's older example claiming
"John's book"→"John is book" is stale for v0.1.73).

## CLI

```bash
echo "I don't think I'll go. That's fine." | python -m tools.contractions expand_contractions
echo "I DON'T THINK I'LL GO." | python -m tools.contractions expand_contractions --preserve_case false
echo "don't" | python -m tools.contractions expand_word
python -m tools.contractions list_contractions
```

**Exit codes:** `0` success · `1` `ValueError` (None/empty input) · `2` `RuntimeError`.

## Requirements / Dependency

- **New dependency:** `contractions` (PyPI) + transitives `textsearch`,
  `anyascii`, `pyahocorasick`. Installed in the Kitbash `.venv` (this is the
  first tools package to require a third-party lib; all earlier tools are pure
  stdlib). Import via the Kitbash `.venv` with the leaked `PYTHONPATH` cleared:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.contractions ...`
- `list_contractions`/`expand_word` membership use the merged library dicts
  (`contractions_dict` + `leftovers_dict` + `slang_dict`). The SPEC's
  `contractions.CONTRACTION_MAP` does not exist in v0.1.73 — do not rely on it.
