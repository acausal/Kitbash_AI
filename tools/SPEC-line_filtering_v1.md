# SPEC: Line Filtering v1

**Module:** `tools/line_filtering/`  
**Status:** Ready for build  
**Dependencies:** stdlib (collections)  
**Priority:** High (foundational data plumbing; enables text processing chains; pairs with Text Search)

---

## Overview

Perform mathematical set operations and ordering on raw text lines. Sort, deduplicate, isolate unique items, count frequencies.

**Design principle:** Simple, composable line operations. Input: newline-delimited text. Output: transformed lines (JSON or plain text).

**Use case:** "Search logs for all 'error' lines, then deduplicate and count frequency of each unique error message."

---

## Scope

### In Scope ✓
- Sort lines (ascending/descending, lexicographic)
- Deduplicate (remove exact duplicates, preserve order or sort)
- Unique (return only items appearing N times)
- Count frequencies (count occurrences of each unique line)
- Reverse (reverse line order)
- Head/Tail (first/last N lines)
- Optional: case-insensitive operations
- Optional: trim whitespace before deduplicating
- Output: JSON or plain text (configurable)

### Out of Scope ✗
- Complex regex patterns (use Text Search for that)
- Fuzzy deduplication or similarity matching
- Numerical sorting (line contents are strings, not numbers)
- Multi-key sorting
- Binary search or indexing
- Streaming/real-time processing

---

## Module Structure

```
tools/line_filtering/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  filter_schema.py               # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `sort_lines(text: str, descending: bool = False, case_insensitive: bool = False) -> dict`

**Purpose:** Sort text lines lexicographically.

**Input:**
- `text` (str): Newline-delimited text
- `descending` (bool): Sort descending (Z→A) instead of ascending (default: False)
- `case_insensitive` (bool): Ignore case for sorting (default: False)

**Output (JSON):**
```json
{
  "operation": "sort_lines",
  "params": {
    "descending": false,
    "case_insensitive": false,
    "total_lines": 10
  },
  "result": {
    "sorted_lines": [
      "apple",
      "banana",
      "cherry",
      "date"
    ],
    "line_count": 4
  }
}
```

**Behavior:**
- Sort lexicographically (Python `sorted()`)
- If case_insensitive, sort by lowercase but preserve original casing in output
- Strip trailing newlines from each line; preserve internal structure

**Error handling:**
- `ValueError` if text is None
- Graceful: empty text → empty output

---

#### 2. `deduplicate_lines(text: str, preserve_order: bool = True, case_insensitive: bool = False) -> dict`

**Purpose:** Remove exact duplicate lines.

**Input:**
- `text` (str): Newline-delimited text
- `preserve_order` (bool): Keep first occurrence position (default: True)
- `case_insensitive` (bool): Treat "Apple" and "apple" as duplicates (default: False)

**Output (JSON):**
```json
{
  "operation": "deduplicate_lines",
  "params": {
    "preserve_order": true,
    "case_insensitive": false,
    "total_lines_input": 10,
    "duplicate_lines": 3
  },
  "result": {
    "deduplicated_lines": [
      "apple",
      "banana",
      "cherry",
      "date"
    ],
    "unique_line_count": 4,
    "duplicates_removed": 3
  }
}
```

**Behavior:**
- Track seen lines (case-sensitive by default)
- Return first occurrence of each unique line
- If preserve_order=False, sort result
- If case_insensitive, deduplicate ignoring case (preserve original casing)

---

#### 3. `count_line_frequency(text: str, sort_by: str = "frequency") -> dict`

**Purpose:** Count occurrence frequency of each unique line.

**Input:**
- `text` (str): Newline-delimited text
- `sort_by` (str): Sort results by `"frequency"` (descending) or `"lexicographic"` (default: `"frequency"`)

**Output (JSON):**
```json
{
  "operation": "count_line_frequency",
  "params": {
    "sort_by": "frequency",
    "total_lines": 15,
    "unique_lines": 4
  },
  "results": {
    "frequency_list": [
      {
        "line": "apple",
        "count": 5,
        "frequency_percent": 33.33
      },
      {
        "line": "banana",
        "count": 4,
        "frequency_percent": 26.67
      },
      {
        "line": "cherry",
        "count": 3,
        "frequency_percent": 20.0
      },
      {
        "line": "date",
        "count": 3,
        "frequency_percent": 20.0
      }
    ],
    "distribution_stats": {
      "most_common": "apple",
      "most_common_count": 5,
      "least_common": "cherry",
      "least_common_count": 3
    }
  }
}
```

**Behavior:**
- Count occurrences of each unique line
- Calculate frequency percentage
- Sort by frequency (descending) or lexicographic order
- Include distribution stats (min, max, mode)

---

#### 4. `filter_by_frequency(text: str, min_count: int = 1, max_count: int = None) -> dict`

**Purpose:** Keep lines that appear N to M times.

**Input:**
- `text` (str): Newline-delimited text
- `min_count` (int): Keep lines appearing ≥ this many times (default: 1)
- `max_count` (int, optional): Keep lines appearing ≤ this many times (default: None = no max)

**Output (JSON):**
```json
{
  "operation": "filter_by_frequency",
  "params": {
    "min_count": 2,
    "max_count": null,
    "total_lines_input": 15,
    "unique_lines_input": 4
  },
  "results": {
    "filtered_lines": [
      "apple",
      "apple",
      "banana",
      "banana",
      "cherry",
      "date"
    ],
    "lines_kept": 6,
    "lines_removed": 9,
    "unique_lines_kept": 4
  }
}
```

**Behavior:**
- Count frequency of each unique line
- Keep lines with count in [min_count, max_count]
- Return all occurrences of kept lines (not deduplicated)
- Useful for "find items that appear more than once" or "find rare items"

---

#### 5. `unique_lines(text: str, case_insensitive: bool = False) -> dict`

**Purpose:** Return lines appearing exactly once (opposite of duplicates).

**Input:**
- `text` (str): Newline-delimited text
- `case_insensitive` (bool): Case-insensitive deduplication check (default: False)

**Output (JSON):**
```json
{
  "operation": "unique_lines",
  "params": {
    "case_insensitive": false,
    "total_lines": 10,
    "unique_items": 4
  },
  "results": {
    "lines_appearing_once": [
      "cherry",
      "date"
    ],
    "count": 2
  }
}
```

**Behavior:**
- Find lines appearing exactly once
- Return those lines

---

#### 6. `head_tail_lines(text: str, n: int = 10, tail: bool = False) -> dict`

**Purpose:** Extract first N or last N lines.

**Input:**
- `text` (str): Newline-delimited text
- `n` (int): Number of lines to extract (default: 10)
- `tail` (bool): Extract last N lines instead of first (default: False)

**Output (JSON):**
```json
{
  "operation": "head_lines",
  "params": {
    "n": 5,
    "tail": false,
    "total_lines": 20
  },
  "results": {
    "extracted_lines": [
      "line1",
      "line2",
      "line3",
      "line4",
      "line5"
    ],
    "count": 5
  }
}
```

**Behavior:**
- Extract first N lines (if tail=False) or last N (if tail=True)
- Handle edge case: N > total_lines (return all)

---

#### 7. `reverse_lines(text: str) -> dict`

**Purpose:** Reverse line order.

**Input:**
- `text` (str): Newline-delimited text

**Output (JSON):**
```json
{
  "operation": "reverse_lines",
  "params": {
    "total_lines": 4
  },
  "results": {
    "reversed_lines": [
      "date",
      "cherry",
      "banana",
      "apple"
    ]
  }
}
```

---

### CLI Interface (in `cli.py`)

```bash
# Sort lines
echo -e "cherry\napple\ndate\nbanana" | python -m tools.line_filtering sort_lines

# Sort descending
echo -e "cherry\napple\ndate" | python -m tools.line_filtering sort_lines --descending

# Deduplicate
echo -e "apple\napple\nbanana\ncherry\napple" \
  | python -m tools.line_filtering deduplicate_lines

# Count frequencies
echo -e "apple\napple\nbanana\napple\ncherry" \
  | python -m tools.line_filtering count_line_frequency --sort_by frequency

# Keep lines appearing 2+ times
echo -e "apple\napple\nbanana\ncherry\napple" \
  | python -m tools.line_filtering filter_by_frequency --min_count 2

# Find lines appearing exactly once
echo -e "apple\napple\nbanana\ncherry" \
  | python -m tools.line_filtering unique_lines

# Get first 5 lines
echo -e "line1\nline2\nline3\nline4\nline5\nline6" \
  | python -m tools.line_filtering head_tail_lines --n 5

# Get last 3 lines
echo -e "line1\nline2\nline3\nline4\nline5" \
  | python -m tools.line_filtering head_tail_lines --n 3 --tail

# Reverse order
echo -e "apple\nbanana\ncherry" \
  | python -m tools.line_filtering reverse_lines
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `filter_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class FrequencyEntry:
    line: str
    count: int
    frequency_percent: float

@dataclass
class DistributionStats:
    most_common: str
    most_common_count: int
    least_common: str
    least_common_count: int

@dataclass
class SortResult:
    sorted_lines: List[str]
    line_count: int

@dataclass
class DeduplicateResult:
    deduplicated_lines: List[str]
    unique_line_count: int
    duplicates_removed: int

@dataclass
class FrequencyResult:
    frequency_list: List[FrequencyEntry]
    distribution_stats: DistributionStats

@dataclass
class FilterByFrequencyResult:
    filtered_lines: List[str]
    lines_kept: int
    lines_removed: int
    unique_lines_kept: int

@dataclass
class UniqueResult:
    lines_appearing_once: List[str]
    count: int

@dataclass
class HeadTailResult:
    extracted_lines: List[str]
    count: int
```

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — invalid input (text is None, invalid n, invalid sort_by, invalid min/max_count)
- `RuntimeError` — internal processing error
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("line_filtering")`
- Events: `filtering_started`, `filtering_complete`, `filtering_failed`
- Metadata: operation, lines_input, lines_output, duplicates_removed, execution_time_ms

---

## Test Cases

### Happy Path (sort_lines)
1. Sort ascending → alphabetical order
2. Sort descending → reverse alphabetical
3. Sort case-insensitive → ignores case in sort key
4. Empty text → zero lines output

### Happy Path (deduplicate_lines)
5. Remove duplicates, preserve order → first occurrence position kept
6. Remove duplicates, don't preserve order → sorted output
7. Case-insensitive dedup → "Apple" and "apple" treated as same
8. No duplicates → unchanged output

### Happy Path (count_line_frequency)
9. Frequency count → correct counts, frequency percentages sum to 100%
10. Sort by frequency → descending by count
11. Sort lexicographic → alphabetical order
12. Most common / least common stats → correct

### Happy Path (filter_by_frequency)
13. min_count=2 → keep lines appearing 2+ times
14. min_count=1, max_count=2 → keep lines appearing 1-2 times
15. No lines match filter → empty output

### Happy Path (unique_lines)
16. Lines appearing once → correct
17. Some duplicates → only truly unique returned

### Happy Path (head_tail_lines)
18. Head n=5 → first 5 lines
19. Tail n=3 → last 3 lines
20. n > total_lines → all lines returned

### Happy Path (reverse_lines)
21. Reverse → correct order

### Edge Cases
22. Single line → operations work on single line
23. Empty text → zero lines
24. Duplicate lines adjacent → dedup works
25. Duplicate lines separated → dedup works
26. All lines identical → dedup returns 1 line
27. Very long lines (1000+ chars) → handled
28. Lines with Unicode → preserved correctly
29. Lines with leading/trailing spaces → preserved (not trimmed by default)
30. Mix of empty and non-empty lines → empty lines treated as valid entries

### Error Cases
31. text is None → `ValueError`
32. Invalid sort_by → `ValueError`
33. n < 0 → `ValueError`
34. min_count < 1 → `ValueError`
35. min_count > max_count → `ValueError`

### CLI Behavior
36. CLI exit code 0 on success
37. CLI exit code 1 on ValueError
38. CLI exit code 2 on RuntimeError
39. CLI reads lines from stdin
40. CLI with combined flags (--case_insensitive --preserve_order) → both applied

---

## Non-Goals (Explicitly Out of Scope)

- Numeric sorting (lines are strings)
- Fuzzy deduplication or similarity matching
- Regex-based filtering (use Text Search)
- Multi-key sorting
- Streaming/real-time processing
- Trimming or normalizing whitespace (preserve as-is)

---

## Implementation Notes

### Deduplication Strategy
- Use `dict.fromkeys()` to preserve order while deduping (O(n) memory, O(n) time)
- For case-insensitive: track lowercase version as key, preserve original casing in output

### Frequency Counting
- Use `collections.Counter` for simplicity
- Calculate percentages as (count / total) * 100

### Head/Tail Efficiency
- For head: slice `lines[:n]`
- For tail: slice `lines[-n:]`
- Handle n > len(lines) gracefully

### Sorting
- Use Python's built-in `sorted()` with optional `key=str.lower` for case-insensitive
- Stable sort; preserves relative order of equal elements

---

## Success Criteria

- ✅ All 40 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Sort order correct (ascending/descending, case-sensitive/insensitive)
- ✅ Deduplication removes exact duplicates
- ✅ Frequency counts accurate; percentages sum to 100%
- ✅ Filtering by frequency includes correct lines
- ✅ Head/tail extract correct slices
- ✅ Reverse reverses line order
- ✅ Edge cases handled gracefully (empty, single line, unicode)
- ✅ Errors logged via structured_logger with context
- ✅ README documents all functions with examples

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
