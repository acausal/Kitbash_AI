# SPEC: Text Search v1

**Module:** `tools/text_search/`  
**Status:** Ready for build  
**Dependencies:** stdlib (re, collections)  
**Priority:** High (foundational data plumbing; enables searching logs, cartridge text, any indexed content)

---

## Overview

Search text for patterns using regular expressions. Return matches with line numbers, surrounding context, and configurable flags (case-insensitive, multiline, etc.).

**Design principle:** Thin wrapper over stdlib `re` module. POSIX grep-like interface via CLI but with JSON I/O for tool composition.

**Use case:** "Search execution logs for all queries mentioning 'photosynthesis', show me line numbers and 3 lines of context around each match."

---

## Scope

### In Scope ✓
- Regex pattern matching (stdlib `re` syntax)
- Return matches with line numbers (1-indexed)
- Optional surrounding context (N lines before/after)
- Case-insensitive flag
- Multiline flag (`.` matches newlines)
- Verbose flag (regex comments)
- Inverse matching (lines NOT matching pattern)
- Output: JSON with matches, line numbers, context

### Out of Scope ✗
- Performance optimization (ripgrep is separate tool if needed)
- Full grep feature parity (lookahead, named groups optional, etc.)
- Binary file handling
- Recursive directory searching (single file/stream only)
- Fuzzy matching or approximate search
- Highlighting or terminal colors

---

## Module Structure

```
tools/text_search/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  search_schema.py               # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `search_text(text: str, pattern: str, case_insensitive: bool = False, multiline: bool = False, verbose: bool = False, inverse: bool = False) -> dict`

**Purpose:** Search text for pattern matches.

**Input:**
- `text` (str): Full text to search
- `pattern` (str): Regex pattern (stdlib `re` syntax)
- `case_insensitive` (bool): Ignore case (flag re.IGNORECASE)
- `multiline` (bool): `.` matches newlines (flag re.DOTALL)
- `verbose` (bool): Allow comments in regex (flag re.VERBOSE)
- `inverse` (bool): Return lines NOT matching pattern

**Output (JSON):**
```json
{
  "search_params": {
    "pattern": "photosynthesis",
    "case_insensitive": false,
    "multiline": false,
    "inverse": false,
    "total_lines_searched": 100
  },
  "results": {
    "total_matches": 3,
    "total_lines_with_matches": 3,
    "matches": [
      {
        "match_number": 1,
        "line_number": 5,
        "matched_text": "photosynthesis occurs in plants",
        "match_position": {
          "start": 0,
          "end": 14
        },
        "context_before": [
          {
            "line_number": 3,
            "text": "plants use energy"
          },
          {
            "line_number": 4,
            "text": "through light reactions"
          }
        ],
        "context_after": [
          {
            "line_number": 6,
            "text": "in chloroplasts"
          },
          {
            "line_number": 7,
            "text": "via the Calvin cycle"
          }
        ]
      },
      {
        "match_number": 2,
        "line_number": 45,
        "matched_text": "photosynthesis requires water",
        "match_position": {
          "start": 0,
          "end": 14
        },
        "context_before": [],
        "context_after": []
      }
    ]
  }
}
```

**Behavior:**
- Split text into lines
- Compile regex with requested flags
- Match each line (or inverse match)
- For each match, include: line number (1-indexed), matched text, position within line
- Include surrounding context lines (configurable count, default: 2)
- Return all matches in order

**Error handling:**
- `ValueError` if regex pattern is invalid (re.error)
- `ValueError` if text is None or empty

---

#### 2. `search_lines(lines: list, pattern: str, context_lines: int = 2, case_insensitive: bool = False, multiline: bool = False, verbose: bool = False, inverse: bool = False) -> dict`

**Purpose:** Search a list of already-split lines (useful for JSONL or line-based input).

**Input:**
- `lines` (list of str): Pre-split text lines
- `pattern` (str): Regex pattern
- `context_lines` (int): Number of lines before/after to include (default: 2)
- Case-insensitive, multiline, verbose, inverse flags (as above)

**Output (JSON):**
```json
{
  "search_params": {
    "pattern": "photosynthesis",
    "context_lines": 2,
    "case_insensitive": false,
    "inverse": false,
    "total_lines_searched": 100
  },
  "results": {
    "total_matches": 3,
    "total_lines_with_matches": 2,
    "matches": [
      {
        "match_number": 1,
        "line_number": 5,
        "matched_text": "photosynthesis occurs in plants",
        "match_position": {
          "start": 0,
          "end": 14
        },
        "context_before": [
          {"line_number": 3, "text": "..."},
          {"line_number": 4, "text": "..."}
        ],
        "context_after": [
          {"line_number": 6, "text": "..."},
          {"line_number": 7, "text": "..."}
        ]
      }
    ]
  }
}
```

**Behavior:**
- Same as `search_text`, but operates on pre-split lines
- Useful for JSONL files, execution logs, or traces where lines are already separated

---

#### 3. `search_and_extract(text: str, pattern: str, group_number: int = 0, case_insensitive: bool = False) -> dict`

**Purpose:** Search and extract capture groups from matches.

**Input:**
- `text` (str): Text to search
- `pattern` (str): Regex with capture groups, e.g., `r'fact_(\d+)→grain_(\d+)'`
- `group_number` (int): Which group to extract (0 = full match, 1+ = capture groups)
- Case-insensitive flag

**Output (JSON):**
```json
{
  "search_params": {
    "pattern": "fact_(\\d+)→grain_(\\d+)",
    "group_number": 0,
    "case_insensitive": false
  },
  "results": {
    "total_matches": 5,
    "extracted_values": [
      {
        "match_number": 1,
        "line_number": 10,
        "full_match": "fact_123→grain_456",
        "extracted_groups": {
          "group_0": "fact_123→grain_456",
          "group_1": "123",
          "group_2": "456"
        }
      },
      {
        "match_number": 2,
        "line_number": 15,
        "full_match": "fact_789→grain_012",
        "extracted_groups": {
          "group_0": "fact_789→grain_012",
          "group_1": "789",
          "group_2": "012"
        }
      }
    ]
  }
}
```

**Behavior:**
- Find all matches
- Extract capture groups
- Return full match + all groups
- Useful for parsing structured data (traces, logs with consistent format)

---

#### 4. `count_matches(text: str, pattern: str, case_insensitive: bool = False) -> dict`

**Purpose:** Count matches without returning full match details (lighter-weight).

**Input:**
- `text` (str): Text to search
- `pattern` (str): Regex pattern
- Case-insensitive flag

**Output (JSON):**
```json
{
  "pattern": "photosynthesis",
  "case_insensitive": false,
  "total_matches": 3,
  "total_lines_searched": 100,
  "lines_with_matches": 3,
  "match_density": 0.03
}
```

**Behavior:**
- Count all matches
- Count unique lines with at least one match
- Return counts + density (matches / total_lines)

**Error handling:**
- `ValueError` if pattern is invalid

---

#### 5. `replace_matches(text: str, pattern: str, replacement: str, case_insensitive: bool = False, count_limit: int = None) -> dict`

**Purpose:** Replace matches with replacement text (for simple transformations).

**Input:**
- `text` (str): Original text
- `pattern` (str): Regex pattern
- `replacement` (str): Replacement string (can include backreferences like `\1`, `\2`)
- `case_insensitive` (bool): Case-insensitive matching
- `count_limit` (int, optional): Limit replacements to first N (default: all)

**Output (JSON):**
```json
{
  "search_params": {
    "pattern": "photosynthesis",
    "replacement": "PHOTOSYNTHESIS",
    "case_insensitive": false,
    "count_limit": null,
    "replacements_made": 3
  },
  "original_text": "photosynthesis is important...",
  "modified_text": "PHOTOSYNTHESIS is important...",
  "changes": [
    {
      "change_number": 1,
      "line_number": 5,
      "original": "photosynthesis occurs",
      "replaced": "PHOTOSYNTHESIS occurs"
    }
  ]
}
```

**Behavior:**
- Replace all matches (or up to count_limit)
- Track each replacement
- Return modified text + change log
- Useful for normalization or data cleaning

**Error handling:**
- `ValueError` if pattern is invalid or replacement backreferences are malformed

---

### CLI Interface (in `cli.py`)

```bash
# Simple pattern search
echo "photosynthesis is important. photosynthesis occurs in plants." \
  | python -m tools.text_search search_text --pattern "photosynthesis"

# Case-insensitive search
echo "Photosynthesis and PHOTOSYNTHESIS are the same." \
  | python -m tools.text_search search_text --pattern "photosynthesis" --case_insensitive

# Search with context
echo -e "line1\nline2\nline3\nphoto here\nline5" \
  | python -m tools.text_search search_text --pattern "photo" --context_lines 2

# Inverse search (lines NOT matching)
echo -e "photo\nnot\nphoto\nmore" \
  | python -m tools.text_search search_text --pattern "photo" --inverse

# Search JSONL lines
cat traces.jsonl | python -m tools.text_search search_lines --pattern "error"

# Extract capture groups
echo "fact_123→grain_456 and fact_789→grain_012" \
  | python -m tools.text_search search_and_extract --pattern 'fact_(\d+)→grain_(\d+)'

# Count matches only
echo "match match nomatch match" \
  | python -m tools.text_search count_matches --pattern "match"

# Replace matches
echo "photosynthesis is cool. photosynthesis rocks." \
  | python -m tools.text_search replace_matches --pattern "photosynthesis" --replacement "photosynthesis"
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `search_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class ContextLine:
    line_number: int
    text: str

@dataclass
class MatchPosition:
    start: int  # character offset in line
    end: int

@dataclass
class Match:
    match_number: int
    line_number: int
    matched_text: str
    match_position: MatchPosition
    context_before: List[ContextLine]
    context_after: List[ContextLine]

@dataclass
class SearchResults:
    total_matches: int
    total_lines_with_matches: int
    matches: List[Match]

@dataclass
class SearchReport:
    search_params: Dict[str, Any]
    results: SearchResults

@dataclass
class ExtractedGroup:
    match_number: int
    line_number: int
    full_match: str
    extracted_groups: Dict[str, str]  # group_0, group_1, group_2, etc.

@dataclass
class CountReport:
    pattern: str
    case_insensitive: bool
    total_matches: int
    total_lines_searched: int
    lines_with_matches: int
    match_density: float

@dataclass
class ReplaceChange:
    change_number: int
    line_number: int
    original: str
    replaced: str

@dataclass
class ReplaceReport:
    search_params: Dict[str, Any]
    original_text: str
    modified_text: str
    changes: List[ReplaceChange]
```

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — invalid regex pattern, invalid backreferences, None/empty text
- `RuntimeError` — internal regex error (should be rare)
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("text_search")`
- Events: `search_started`, `search_complete`, `search_failed`, `replace_complete`
- Metadata: pattern, total_lines, matches_found, replacements_made, execution_time_ms

---

## Test Cases

### Happy Path (search_text)
1. Simple pattern match → correct line number and matched text
2. Multiple matches on same line → all captured
3. Multiple matches across lines → all with correct line numbers
4. Pattern at start of line → position 0
5. Pattern at end of line → end position correct
6. Case-sensitive by default → case matters
7. Case-insensitive flag → ignores case
8. Context included (context_lines=2) → 2 lines before/after
9. Match at start of file (no context before) → context_before empty
10. Match at end of file (no context after) → context_after empty

### Happy Path (other functions)
11. search_lines with JSONL → correct parsing
12. search_and_extract with groups → all groups returned
13. count_matches → density calculated correctly
14. replace_matches → all replacements made
15. replace_matches with limit → only first N replaced

### Edge Cases
16. Empty pattern (matches everything) → undefined behavior, document or error
17. Pattern matches empty string → depends on regex
18. No matches → total_matches = 0, empty matches array
19. Match on every line → total_lines_with_matches = total_lines
20. Very long line (1000+ chars) → handled without truncation
21. Context lines requested but not available → graceful (empty lists)
22. Backreferences in replacement (\1, \2) → correctly substituted
23. Case-insensitive with Unicode → handled correctly
24. Multiline flag with pattern `.` → `.` matches `\n`
25. Verbose flag with regex comments → comments ignored

### Error Cases
26. Invalid regex (unclosed bracket) → `ValueError`
27. Invalid backreference in replacement (\99 doesn't exist) → `ValueError`
28. Text is None → `ValueError`
29. Text is empty string → acceptable (zero lines)
30. Pattern is None → `ValueError`
31. Pattern is empty string → acceptable (matches everything)
32. Invalid context_lines (negative) → `ValueError`
33. Inverse flag with zero matches → returns all lines

### CLI Behavior
34. CLI exit code 0 on success
35. CLI exit code 1 on ValueError
36. CLI exit code 2 on RuntimeError
37. CLI reads multiline text from stdin
38. CLI with --pattern only → uses default flags
39. CLI with multiple flags (--case_insensitive --inverse) → both applied

---

## Non-Goals (Explicitly Out of Scope)

- Performance optimization beyond stdlib `re`
- Full grep/ripgrep feature parity
- Binary file handling
- Recursive directory searching
- Fuzzy or approximate matching
- Highlighting or terminal colors
- Named capture groups (standard Python syntax supported, but not specially handled)

---

## Implementation Notes

### Regex Flags
- Combine flags using `re.IGNORECASE | re.DOTALL | re.VERBOSE`
- Apply all requested flags to compiled regex

### Line Numbering
- Lines are 1-indexed (first line is line 1, not 0)
- Maintain line number tracking throughout

### Context Extraction
- Extract `context_lines` lines before and after match
- Handle boundaries (start of file, end of file)
- Return empty lists if no context available

### Match Position
- `start` is character offset in the matched line (0-indexed within line)
- `end` is character offset after match
- Useful for highlighting or sub-string extraction

### Backreferences
- Support Python regex backreferences: `\1`, `\2`, etc.
- Also support group names if pattern uses `(?P<name>...)`
- Validate backreferences exist in pattern before replacement

### Unicode Handling
- Python 3 `re` module handles Unicode by default
- Case-insensitive matching works correctly with Unicode

---

## Success Criteria

- ✅ All 39 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Line numbers 1-indexed (first line is 1, not 0)
- ✅ Context correctly extracted (no overlaps, empty lists at boundaries)
- ✅ Capture groups extracted correctly (all groups returned)
- ✅ Replacements made accurately with backreferences
- ✅ Flags (case-insensitive, multiline, verbose) applied correctly
- ✅ Error messages clear and actionable
- ✅ Errors logged via structured_logger
- ✅ README documents all functions, examples, and common patterns

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
