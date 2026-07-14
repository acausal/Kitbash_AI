# csv_operations

Stdlib-only (`csv`, `json`, `re`) CSV plumbing for the tools ecosystem — parse,
filter, select, sort, unique, and profile CSVs, emitting JSON for downstream
tools (json_query_filter, filesystem_access). No pandas; loads the whole file
into memory (v1). Isolation-first.

## Library

```python
from tools.csv_operations import (
    parse_csv, filter_rows, select_columns, sort_rows, unique_values, csv_stats,
)

# parse (raw text or --file)
p   = parse_csv(data="name,age\nAlice,30\nBob,25", has_header=True)
rows = p["rows"]                       # list of dicts

# filter (ops: == != > < >= <= regex)
f   = filter_rows(rows, "age", ">", "25")
# select / exclude
s   = select_columns(rows, ["name", "email"])
sx  = select_columns(rows, ["age", "active"], exclude=True)
# sort (stable; numeric=convert to float)
so  = sort_rows(rows, "age", numeric=True)
# unique values + counts (sorted by count desc)
u   = unique_values(rows, "active")
# column profiling (type inference + min/max + samples)
st  = csv_stats(rows)
```

Every function returns a **plain JSON-serializable dict** with an `operation`
key plus input/output metadata.

### Behavior notes
- **Dialect detection:** `csv.Sniffer` auto-detects delimiter/quote/escape; an
  explicit `--delimiter` overrides it; comma is the fallback. BOM is stripped.
- **NULL tokens** (`""`, `NULL`, `null`, `N/A`, `n/a`, `NA`, `na`) normalize to
  the empty string so downstream ops treat missing values uniformly.
- **Headerless CSVs** get synthesized keys `col_1`, `col_2`, ...
- **Type inference:** a column is `numeric` if its first 5 non-empty values all
  parse as `float()`; otherwise `text`. `csv_stats` reports `min`/`max` (floats)
  for numeric columns.
- **Filter numeric ops** (`> < >= <=`) compare as numbers when both sides parse,
  else fall back to string comparison. `regex` uses `re.search`.
- **Sort** is stable (Python Timsort). `numeric=True` raises `ValueError` naming
  the offending row if any non-numeric value appears.

### Error taxonomy (exit codes)
`ValueError` → CLI 1 (malformed CSV, missing column, invalid operator, both/
neither source) · `FileNotFoundError` → CLI 2 · `OSError`/`RuntimeError` → CLI 3
(bad regex, IO failure).

## CLI

```bash
echo "name,age,email\nAlice,30,a@x.com\nBob,25,b@x.com" | python -m tools.csv_operations parse_csv
python -m tools.csv_operations filter_rows --file data.csv --column age --operator ">" --value 25
python -m tools.csv_operations select_columns --file data.csv --columns name email
python -m tools.csv_operations sort_rows --file data.csv --column age --numeric
python -m tools.csv_operations unique_values --file data.csv --column active
python -m tools.csv_operations csv_stats --file data.csv
```

**Exit codes:** `0` success · `1` `ValueError` · `2` `FileNotFoundError` · `3` `IOError`/`RuntimeError`.

## Requirements

- Pure stdlib (`csv`, `json`, `re`). No new deps.
- In the Kitbash `.venv`, clear the leaked `PYTHONPATH` when invoking:
  `PYTHONPATH= .venv/Scripts/python.exe -m tools.csv_operations ...`
