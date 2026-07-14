# SPEC: CSV Operations v1

**Module:** `tools/csv_operations/`  
**Status:** Ready for build  
**Dependencies:** stdlib (csv, json)  
**Priority:** High (foundational data plumbing; pairs with document extractors and filesystem access)

---

## Overview

Parse, filter, select columns, sort, and transform CSV data using deterministic operations. Lightweight alternative to pandas for common CSV workflows. Works with CSV files or raw CSV text; outputs normalized JSON for downstream tools.

**Design principle:** Stdlib-only, composable operations (filter rows, select columns, sort). Fail-loud on malformed CSV. Chain operations via pipes.

**Use case:** "Extract data from CSV; filter to relevant rows; select specific columns; sort by date; pass to JSON Query/Filter tool for further analysis."

---

## Scope

### In Scope ✓
- Parse CSV from file or raw text
- Detect dialect (delimiter, quote char, escape)
- Filter rows (simple conditions: column == value, column != value, column > value, column < value, regex match)
- Select/exclude columns
- Sort by one or more columns (ascending/descending)
- Aggregate (count rows, unique values per column, group by)
- Output formats: JSON array, CSV, summary stats
- Handle headers and headerless CSVs
- Trim whitespace from values
- Type inference (try to detect numeric vs text)

### Out of Scope ✗
- Complex aggregations (sum, avg, pivot tables) — use Tier 2 tools
- Custom formulas or computed columns
- Unicode encoding edge cases (handle UTF-8, warn on others)
- Very large files (streaming) — v1 loads entire file
- SQL-like JOINs between CSVs

---

## Module Structure

```
tools/csv_operations/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  csv_parser.py                  # CSV parsing, dialect detection
  filters.py                     # row filtering logic
  cli.py                         # argparse CLI
  csv_schema.py                  # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `parse_csv(data: str, file_path: str = None, has_header: bool = True, delimiter: str = None) -> dict`

**Purpose:** Parse CSV text or file into normalized rows with headers.

**Input:**
- `data` (str): Raw CSV text (if file_path not provided)
- `file_path` (str, optional): Path to CSV file (if data not provided)
- `has_header` (bool): Whether first row is header (default: True)
- `delimiter` (str, optional): CSV delimiter (auto-detect if None)

**Output (JSON):**
```json
{
  "operation": "parse_csv",
  "row_count": 3,
  "column_count": 4,
  "has_header": true,
  "delimiter": ",",
  "headers": ["name", "age", "email", "active"],
  "rows": [
    {
      "name": "Alice",
      "age": "30",
      "email": "alice@example.com",
      "active": "true"
    },
    {
      "name": "Bob",
      "age": "25",
      "email": "bob@example.com",
      "active": "false"
    },
    {
      "name": "Charlie",
      "age": "35",
      "email": "charlie@example.com",
      "active": "true"
    }
  ]
}
```

**Behavior:**
- Parse CSV (detect dialect if not specified)
- Extract headers (if present)
- Convert each row to dict (headers as keys)
- Trim whitespace from values
- Return rows + metadata

**Error handling:**
- `FileNotFoundError` if file_path specified but not found
- `ValueError` if both data and file_path None, or CSV is malformed
- `IOError` if file read fails

---

#### 2. `filter_rows(rows: list, column: str, operator: str, value: str) -> dict`

**Purpose:** Filter rows based on column condition.

**Input:**
- `rows` (list): List of row dicts (from parse_csv)
- `column` (str): Column name to filter on
- `operator` (str): Comparison operator: "==", "!=", ">", "<", ">=", "<=", "regex"
- `value` (str): Value to compare against (or regex pattern if operator="regex")

**Output (JSON):**
```json
{
  "operation": "filter_rows",
  "filter": {
    "column": "age",
    "operator": ">",
    "value": "25"
  },
  "input_row_count": 3,
  "output_row_count": 2,
  "rows": [
    {
      "name": "Alice",
      "age": "30",
      "email": "alice@example.com",
      "active": "true"
    },
    {
      "name": "Charlie",
      "age": "35",
      "email": "charlie@example.com",
      "active": "true"
    }
  ]
}
```

**Behavior:**
- Apply condition to each row
- For numeric operators (>, <, >=, <=): attempt numeric comparison; fall back to string if parse fails
- For "==", "!=": string comparison
- For "regex": re.search() on column value
- Return filtered rows + metadata

**Error handling:**
- `ValueError` if column not found, invalid operator
- `RuntimeError` if regex is invalid

---

#### 3. `select_columns(rows: list, columns: list = None, exclude: bool = False) -> dict`

**Purpose:** Select or exclude specific columns.

**Input:**
- `rows` (list): List of row dicts
- `columns` (list): Column names to keep (or exclude if exclude=True)
- `exclude` (bool): If True, exclude the specified columns; if False, keep only them (default: False)

**Output (JSON):**
```json
{
  "operation": "select_columns",
  "columns": ["name", "email"],
  "exclude": false,
  "input_column_count": 4,
  "output_column_count": 2,
  "rows": [
    {
      "name": "Alice",
      "email": "alice@example.com"
    },
    {
      "name": "Bob",
      "email": "bob@example.com"
    }
  ]
}
```

**Behavior:**
- Keep only specified columns (or all except specified if exclude=True)
- Preserve order (columns in specified order)
- Return rows with selected columns only

**Error handling:**
- `ValueError` if any specified column not found in rows

---

#### 4. `sort_rows(rows: list, column: str, descending: bool = False, numeric: bool = False) -> dict`

**Purpose:** Sort rows by a column.

**Input:**
- `rows` (list): List of row dicts
- `column` (str): Column name to sort by
- `descending` (bool): Sort descending if True (default: False = ascending)
- `numeric` (bool): Treat values as numeric (default: False = string sort)

**Output (JSON):**
```json
{
  "operation": "sort_rows",
  "column": "age",
  "descending": false,
  "numeric": true,
  "rows": [
    {
      "name": "Bob",
      "age": "25",
      "email": "bob@example.com",
      "active": "false"
    },
    {
      "name": "Alice",
      "age": "30",
      "email": "alice@example.com",
      "active": "true"
    },
    {
      "name": "Charlie",
      "age": "35",
      "email": "charlie@example.com",
      "active": "true"
    }
  ]
}
```

**Behavior:**
- Sort rows by column value
- If numeric=True, convert to int/float for comparison
- If numeric=False, string sort
- Preserve order of equal values (stable sort)

**Error handling:**
- `ValueError` if column not found
- `ValueError` if numeric=True but values can't be converted to numbers (show which rows)

---

#### 5. `unique_values(rows: list, column: str) -> dict`

**Purpose:** Get unique values in a column.

**Input:**
- `rows` (list): List of row dicts
- `column` (str): Column name

**Output (JSON):**
```json
{
  "operation": "unique_values",
  "column": "active",
  "total_rows": 3,
  "unique_count": 2,
  "values": ["true", "false"],
  "value_counts": {
    "true": 2,
    "false": 1
  }
}
```

**Behavior:**
- Extract unique values from column
- Count occurrences of each value
- Return sorted by count (descending)

---

#### 6. `csv_stats(rows: list) -> dict`

**Purpose:** Generate summary statistics for CSV data.

**Input:**
- `rows` (list): List of row dicts

**Output (JSON):**
```json
{
  "operation": "csv_stats",
  "row_count": 3,
  "column_count": 4,
  "columns": {
    "name": {
      "type": "text",
      "unique_count": 3,
      "sample_values": ["Alice", "Bob", "Charlie"]
    },
    "age": {
      "type": "numeric",
      "unique_count": 3,
      "min": 25,
      "max": 35,
      "sample_values": ["30", "25", "35"]
    },
    "email": {
      "type": "text",
      "unique_count": 3,
      "sample_values": ["alice@example.com", "bob@example.com", "charlie@example.com"]
    },
    "active": {
      "type": "text",
      "unique_count": 2,
      "sample_values": ["true", "false"]
    }
  }
}
```

**Behavior:**
- Analyze each column
- Infer type (text vs numeric)
- Report unique count, min/max (if numeric), sample values
- Useful for data profiling

---

### CLI Interface (in `cli.py`)

```bash
# Parse CSV file
python -m tools.csv_operations parse_csv --file data.csv

# Parse raw CSV text
echo "name,age,email
Alice,30,alice@example.com
Bob,25,bob@example.com" | python -m tools.csv_operations parse_csv

# Parse without header
echo "Alice,30,alice@example.com
Bob,25,bob@example.com" | python -m tools.csv_operations parse_csv --has_header false

# Filter rows (age > 25)
python -m tools.csv_operations filter_rows \
  --file data.csv \
  --column age \
  --operator ">" \
  --value 25

# Filter with regex (email contains @example.com)
python -m tools.csv_operations filter_rows \
  --file data.csv \
  --column email \
  --operator regex \
  --value "@example.com"

# Select columns
python -m tools.csv_operations select_columns \
  --file data.csv \
  --columns name email

# Exclude columns
python -m tools.csv_operations select_columns \
  --file data.csv \
  --columns age active \
  --exclude

# Sort by age (numeric)
python -m tools.csv_operations sort_rows \
  --file data.csv \
  --column age \
  --numeric

# Sort by name descending
python -m tools.csv_operations sort_rows \
  --file data.csv \
  --column name \
  --descending

# Get unique values
python -m tools.csv_operations unique_values \
  --file data.csv \
  --column active

# Generate stats
python -m tools.csv_operations csv_stats --file data.csv
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → file not found (FileNotFoundError)
- `3` → internal error (IOError, RuntimeError)

---

### Schema (in `csv_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class ColumnStats:
    type: str  # "text", "numeric"
    unique_count: int
    sample_values: List[str]
    min: Optional[float] = None
    max: Optional[float] = None

@dataclass
class ParseResult:
    operation: str
    row_count: int
    column_count: int
    has_header: bool
    delimiter: str
    headers: List[str]
    rows: List[Dict[str, str]]

@dataclass
class FilterResult:
    operation: str
    filter: Dict[str, str]  # {column, operator, value}
    input_row_count: int
    output_row_count: int
    rows: List[Dict[str, str]]

@dataclass
class SelectResult:
    operation: str
    columns: List[str]
    exclude: bool
    input_column_count: int
    output_column_count: int
    rows: List[Dict[str, str]]

@dataclass
class SortResult:
    operation: str
    column: str
    descending: bool
    numeric: bool
    rows: List[Dict[str, str]]

@dataclass
class UniqueResult:
    operation: str
    column: str
    total_rows: int
    unique_count: int
    values: List[str]
    value_counts: Dict[str, int]

@dataclass
class StatsResult:
    operation: str
    row_count: int
    column_count: int
    columns: Dict[str, ColumnStats]
```

---

## Supported Operators

| Operator | Meaning | Type |
|----------|---------|------|
| `==` | Equals | String/Numeric |
| `!=` | Not equals | String/Numeric |
| `>` | Greater than | Numeric (string fallback) |
| `<` | Less than | Numeric (string fallback) |
| `>=` | Greater or equal | Numeric (string fallback) |
| `<=` | Less or equal | Numeric (string fallback) |
| `regex` | Regex match | String pattern |

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — CSV file not found
- `ValueError` — malformed CSV, missing column, invalid operator
- `IOError` — file read/write error
- `RuntimeError` — internal error (should be rare)

**Logging:**
- Use `structured_logger.get_event_logger("csv_operations")`
- Events: `parse_started`, `parse_complete`, `filter_applied`, `sort_applied`, `stats_generated`
- Metadata: row_count, column_count, operation, execution_time_ms

---

## Test Cases

### Happy Path (parse_csv)
1. Parse simple CSV with header
2. Parse CSV with different delimiter (semicolon, tab)
3. Parse headerless CSV (has_header=False)
4. Parse with quoted values containing commas
5. Parse with newlines inside quoted values
6. Whitespace trimmed from values
7. Empty CSV (just headers)
8. Single-column CSV
9. Single-row CSV (+ header)

### Happy Path (filter_rows)
10. Filter == (string match)
11. Filter != (not equal)
12. Filter > (numeric comparison)
13. Filter < (numeric comparison)
14. Filter regex (pattern match)
15. Filter returns zero rows
16. Filter returns all rows
17. Filter with missing values (NULL, empty string)

### Happy Path (select_columns)
18. Select subset of columns
19. Select preserves order
20. Select single column
21. Exclude columns (exclude=True)
22. Exclude all but one column

### Happy Path (sort_rows)
23. Sort ascending (numeric)
24. Sort descending (numeric)
25. Sort ascending (string)
26. Sort descending (string)
27. Sort with NULL values (treat as empty string)
28. Stable sort (equal values maintain order)

### Happy Path (unique_values)
29. Count unique values
30. Value counts correct
31. Return sorted by count (descending)
32. Unique on column with all same value

### Happy Path (csv_stats)
33. Detect numeric column
34. Detect text column
35. Calculate min/max for numeric
36. Sample values included
37. Stats on empty CSV

### Edge Cases
38. CSV with BOM (byte order mark)
39. CSV with CRLF line endings
40. CSV with just LF line endings
41. CSV with quoted empty fields
42. CSV with escaped quotes
43. Very long lines (1000+ chars)
44. Very large file (1000+ rows) — handled quickly
45. Unicode characters in data
46. Special characters (newline, quote, etc.)

### Error Cases
47. Malformed CSV (unclosed quote) → ValueError
48. File not found → FileNotFoundError
49. Filter on non-existent column → ValueError
50. Select non-existent column → ValueError
51. Sort on non-existent column → ValueError
52. Numeric sort on non-numeric data → ValueError with row details
53. Invalid regex in filter → RuntimeError
54. Empty data string → ValueError (or handle gracefully)
55. Both data and file_path provided → ValueError
56. Neither data nor file_path → ValueError

### CLI Behavior
57. CLI exit code 0 on success
58. CLI exit code 1 on ValueError
59. CLI exit code 2 on FileNotFoundError
60. CLI exit code 3 on IOError/RuntimeError
61. CLI reads CSV from stdin or file
62. CLI outputs JSON to stdout
63. CLI --help documents all options

---

## Non-Goals (Explicitly Out of Scope)

- Complex aggregations (sum, avg, pivot)
- Custom formulas or computed columns
- SQL JOINs between CSVs
- Streaming large files (load entire file into memory)
- Advanced encoding detection (UTF-8 only, warn on others)

---

## Implementation Notes

### CSV Dialect Detection

Use stdlib `csv.Sniffer` to auto-detect delimiter, quote char, and escape char. If detection fails, default to comma-delimited.

```python
import csv
sample = data[:1024]  # First 1KB
try:
    dialect = csv.Sniffer().sniff(sample)
except csv.Error:
    dialect = csv.excel  # default
```

### Type Inference

For numeric detection, try `float()` conversion on a sample of column values (first 5 non-empty values). If all convert, type=numeric; else type=text.

### Handling NULL/Empty Values

Treat empty string, "NULL", "null", "N/A", "n/a" as missing values. Document behavior in README.

---

## Success Criteria

- ✅ All 63 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2, 3)
- ✅ Parsing works with common CSV formats
- ✅ Filtering, selecting, sorting work correctly
- ✅ Stats generation accurate
- ✅ Errors logged via structured_logger with context
- ✅ Handles edge cases (quotes, newlines, unicode, large files)
- ✅ README documents all functions, operators, examples
- ✅ Composable with other tools (JSON Query/Filter, Filesystem Access)

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
