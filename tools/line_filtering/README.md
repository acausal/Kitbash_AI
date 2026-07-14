# line_filtering

Set operations + ordering over newline-delimited text. Pairs with `text_search`
in text-processing chains (search → dedupe → count → head/tail). Isolation-first
(stdlib `collections` only + optional `structured_logger`).

## Library

```python
from tools.line_filtering import (
    sort_lines, deduplicate_lines, count_line_frequency, filter_by_frequency,
    unique_lines, head_tail_lines, reverse_lines,
)

s  = sort_lines("cherry\napple\ndate", descending=True)
d  = deduplicate_lines("apple\napple\nbanana", preserve_order=True)
c  = count_line_frequency("apple\napple\nbanana", sort_by="frequency")
f  = filter_by_frequency("apple\napple\nbanana\ncherry", min_count=2)
u  = unique_lines("apple\napple\nbanana\ncherry")
h  = head_tail_lines("l1\nl2\nl3\nl4\nl5", n=2, tail=False)
r  = reverse_lines("a\nb\nc")
```

Every function returns a **plain JSON-serializable dict**. Behaviour:

- Lines split on `"\n"`; trailing newline stripped. **No whitespace trim** by
  default (case 29). Empty text → zero lines (no error). `text=None` → `ValueError`.
- `sort_lines` — `sorted()`; `case_insensitive` sorts by lowercase but preserves
  original casing.
- `deduplicate_lines` — `dict.fromkeys` preserves first occurrence; `preserve_order=False`
  sorts; case-insensitive dedupes by lowercase, keeps first-casing.
- `count_line_frequency` — `Counter` counts + `frequency_percent` (count/total*100);
  `sort_by="frequency"` → descending count (tie-break lexicographic); `"lexicographic"`
  → A→Z. `distribution_stats` has most/least common (ties → lexicographic first).
- `filter_by_frequency` — keeps all occurrences of lines with
  `min_count <= count <= max_count`; returns **non-deduplicated** kept lines.
- `unique_lines` — lines appearing exactly once.
- `head_tail_lines` — `lines[:n]` / `lines[-n:]`; `n > total` → all; `n=0` → none.
- `reverse_lines` — reversed copy.

## CLI

Reads raw text from **stdin**, writes JSON to **stdout**:

```bash
echo -e "cherry\napple\ndate" | python -m tools.line_filtering sort_lines --descending
echo -e "apple\napple\nbanana" | python -m tools.line_filtering deduplicate_lines
echo -e "apple\napple\nbanana" | python -m tools.line_filtering count_line_frequency --sort_by frequency
echo -e "apple\napple\nbanana\ncherry" | python -m tools.line_filtering filter_by_frequency --min_count 2
echo -e "apple\napple\nbanana\ncherry" | python -m tools.line_filtering unique_lines
echo -e "l1\nl2\nl3\nl4\nl5" | python -m tools.line_filtering head_tail_lines --n 2 --tail
echo -e "a\nb\nc" | python -m tools.line_filtering reverse_lines
```

Flags: `--descending`, `--case_insensitive`, `--no_preserve` (dedup sort),
`--sort_by frequency|lexicographic`, `--min_count N`, `--max_count N`, `--n N`,
`--tail`.

**Exit codes:** `0` success · `1` invalid input (`ValueError`) ·
`2` internal error (`RuntimeError`).

## Requirements

- Pure stdlib (`collections`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.line_filtering ...`
