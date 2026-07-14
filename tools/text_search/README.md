# text_search

Regex search over text — a thin, composable wrapper over the stdlib `re` module.
POSIX grep-like semantics with JSON I/O for tool chaining. Foundational data
plumbing: search logs, cartridge text, traces, or any indexed content.
Isolation-first (stdlib only + optional `structured_logger`).

## Library

```python
from tools.text_search import (
    search_text, search_lines, search_and_extract, count_matches, replace_matches,
)

hits = search_text(text, r"photosynthesis", context_lines=2, case_insensitive=True)
ln   = search_lines(lines, r"error", context_lines=1, inverse=True)
grp  = search_and_extract(text, r"fact_(\d+)→grain_(\d+)", group_number=1)
cnt  = count_matches(text, r"match")
rep  = replace_matches(text, r"photo", "PHOTO", count_limit=2)
```

Every function returns a **plain JSON-serializable dict**. Lines are **1-indexed**.

### Functions

- **search_text / search_lines** — per-line regex; each match carries
  `line_number`, `matched_text` (the full line), `match_position` (0-indexed
  `start`/`end` within the line), and `context_before`/`context_after`
  (`context_lines` each, default 2; empty at file boundaries). `inverse=True`
  returns lines that do **not** match.
- **search_and_extract** — capture-group extraction; each hit has `full_match`
  and `extracted_groups` (`group_0` = full match, `group_1..n` = captures) plus
  the requested `group_number`.
- **count_matches** — lightweight counts + `match_density` (matches / total_lines).
- **replace_matches** — `re.sub`-style replacement with backreferences (`\1`);
  `count_limit` caps total replacements; returns `modified_text` + per-line `changes`.

### Flags

`case_insensitive` → `re.IGNORECASE`; `multiline` → `re.DOTALL` (`.` matches
newlines, per SPEC naming); `verbose` → `re.VERBOSE`.

### Errors & edge cases

- Invalid regex, invalid backreference, `text=None`, `pattern=None`,
  negative `context_lines`/`group_number`/`count_limit` → `ValueError`.
- Empty `text` → zero lines (OK); empty `pattern` → matches everything (OK).
- `inverse` with zero matches → all lines returned.

## CLI

Reads raw text from **stdin**, writes JSON to **stdout**:

```bash
echo "photosynthesis occurs in plants" | python -m tools.text_search search_text --pattern photosynthesis
echo -e "l1\nl2\nphoto\nl4" | python -m tools.text_search search_text --pattern photo --context_lines 1
echo -e "photo\nno\nphoto" | python -m tools.text_search search_text --pattern photo --inverse
echo "fact_123→grain_456" | python -m tools.text_search search_and_extract --pattern 'fact_(\d+)→grain_(\d+)'
echo "a a b a" | python -m tools.text_search count_matches --pattern a
echo "photo photo" | python -m tools.text_search replace_matches --pattern photo --replacement PHOTO --count_limit 1
```

Flags: `--case_insensitive --multiline --verbose --inverse`,
`--context_lines N`, `--group_number N`, `--count_limit N`, `--replacement STR`.

**Exit codes:** `0` success · `1` invalid input (`ValueError`) ·
`2` internal error (`RuntimeError`).

## Requirements

- Pure stdlib (`re`, `collections`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.text_search ...`
