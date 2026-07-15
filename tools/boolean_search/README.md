# boolean_search

Boolean query search over a tokenized corpus (Historical AI batch). AND/OR/NOT
+ parentheses, recursive-descent parser. Stateless, deterministic, stdlib-only.
See SPEC-boolean_search_v1.md and the shared Historical AI contract.

## Library

```python
from tools.boolean_search import search, parse_query, execute_query
r = search("(ai OR ml) AND NOT spam", [{"id":"d1","tokens":["ai","ml"]},{"id":"d2","tokens":["spam"]}], {})
#   r["results"]: matching docs, scored by # distinct matched terms
#   r["parsed_query"]: AST as nested dict
ast = parse_query("(ai OR ml) AND NOT spam")      # AST only
hit = execute_query(ast["parsed_query"], ["ai","ml"])   # evaluate one doc's tokens
```

Precedence: NOT > AND > OR. Parentheses group. Quoted terms supported.

## CLI

```bash
echo '{"query":"(ai OR ml) AND NOT spam","corpus":[...]}' | python -m tools.boolean_search
python -m tools.boolean_search --query "(ai OR ml) AND NOT spam" --input corpus.json
python -m tools.boolean_search --parse --query "(ai OR ml) AND NOT spam"
```

Shared boilerplate (config normalize, stopwords, envelope, CLI/error) lives in
`tools/historical_common.py`. Envelope + shared config apply; exit 0/1/2.

## Notes
- `search` score = number of distinct matched TERM leaves (ties broken by doc_id).
- Syntax errors raise ValueError -> exit 1 with JSON error on stderr.
- `run_id`/`timestamp` differ per call; results are fully deterministic.
