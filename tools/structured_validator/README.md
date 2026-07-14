# structured_validator

Generic Lark-grammar validation (v1). Part of the input-sieve / document-
preprocessing pipeline: validates structured text against a user-supplied Lark
EBNF grammar, returning a parse tree or a clear error. Isolation-first tool —
stdlib + Lark + optional `structured_logger` only.

v1 is infrastructure: **no built-in grammars** (those come as use cases emerge).
It accepts an inline grammar or a `.lark` file and returns the parse result.

## Library

```python
from tools.structured_validator import validate_input, ParseResult

grammar = '''
?start: greeting " " name
greeting: "hello" | "hi" | "hey"
name: /[A-Z][a-z]+/
'''
r = validate_input("hello Alice", grammar)
# r.success == True, r.parse_tree == {"data":"start","children":[...]}

r = validate_input("goodbye Alice", grammar)
# r.success == False, r.error == "..."
```

`validate_input(text, grammar, grammar_start="start") -> ParseResult`

- `grammar`: inline EBNF string, or a path to a `.lark` file. A bare string with
  no newline that exists as a file is treated as a path.
- `parse_tree` is a **JSON-serializable dict** (`{data, children}`), not a live
  Lark `Tree`, so it survives `to_dict()`/JSON export. `None` on failure.
- Raises `ValueError` (text None/non-str, or invalid grammar EBNF),
  `FileNotFoundError` (grammar file missing).

## CLI

```bash
python -m tools.structured_validator input.txt --grammar grammars/greeting.lark
python -m tools.structured_validator input.txt --grammar-string 'start: "hi"'
python -m tools.structured_validator input.txt -g inline.txt --output result.json
```

Writes JSON ParseResult to `--output` (or stdout) and a summary to stderr.
**Exit codes:** `0` parse succeeded · `1` validation failed (parse error) ·
`2` grammar/file/input error.

## Requirements

- `lark` (PyPI, pure-Python). Install in the Kitbash `.venv`:
  `uv pip install lark`.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.structured_validator ...`
