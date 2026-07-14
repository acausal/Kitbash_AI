# SPEC: Contractions v1

**Module:** `tools/contractions/`  
**Status:** Ready for build  
**Dependencies:** `contractions` (PyPI, lightweight)  
**Priority:** High (improves negation_detector accuracy; preprocessing step for tokenizer)

---

## Overview

Expand English contractions ("don't" → "do not", "I'll" → "I will") using deterministic rule-based substitution. Preprocessing step before tokenization and negation detection.

**Design principle:** Lightweight, deterministic, no neural networks. Uses the `contractions` library (pure Python, ~5KB) which implements a comprehensive contraction dictionary.

**Use case:** "Normalize user input before feeding to tokenizer/negation_detector; 'don't know' → 'do not know' improves negation window detection."

---

## Scope

### In Scope ✓
- Expand common English contractions (I'll, don't, can't, won't, etc.)
- Preserve original text case (I'VE → I HAVE, I've → I have)
- Handle possessives ('s, 's not, etc.)
- Optional: preserve contracted form in output (for analysis)
- Output: expanded text or dict with both forms
- Works on full text or per-word

### Out of Scope ✗
- Other languages (French, Spanish contractions)
- Slang or non-standard contractions
- Custom user-defined contractions (v2)
- Inverse operation (expand → contract)

---

## Module Structure

```
tools/contractions/
  __init__.py                    # exports main functions
  core.py                        # implementation logic
  cli.py                         # argparse CLI
  contractions_schema.py         # dataclasses for JSON output
  README.md                       # usage docs
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `expand_contractions(text: str, preserve_case: bool = True) -> dict`

**Purpose:** Expand all contractions in text.

**Input:**
- `text` (str): Text containing contractions
- `preserve_case` (bool): Maintain original casing (default: True)

**Output (JSON):**
```json
{
  "operation": "expand_contractions",
  "preserve_case": true,
  "original_text": "I don't think I'll go. That's fine.",
  "expanded_text": "I do not think I will go. That is fine.",
  "contractions_found": 3,
  "contractions_list": [
    {
      "contraction": "don't",
      "expansion": "do not",
      "position": 2
    },
    {
      "contraction": "I'll",
      "expansion": "I will",
      "position": 8
    },
    {
      "contraction": "That's",
      "expansion": "That is",
      "position": 12
    }
  ]
}
```

**Behavior:**
- Find all contractions in text using `contractions` library
- Replace with expanded forms
- Preserve original casing if flag set
- Track all replacements with positions
- Return expanded text + metadata

**Error handling:**
- `ValueError` if text is None or empty
- `RuntimeError` if contraction library fails (rare)

---

#### 2. `expand_word(word: str, preserve_case: bool = True) -> dict`

**Purpose:** Expand a single word (if it's a contraction).

**Input:**
- `word` (str): Single word or phrase (e.g., "don't")
- `preserve_case` (bool): Maintain original casing (default: True)

**Output (JSON):**
```json
{
  "operation": "expand_word",
  "word": "don't",
  "is_contraction": true,
  "expanded": "do not",
  "case_preserved": true
}
```

Or if not a contraction:
```json
{
  "operation": "expand_word",
  "word": "hello",
  "is_contraction": false,
  "expanded": "hello"
}
```

**Behavior:**
- Check if word is a known contraction
- If yes, return expansion; if no, return word unchanged
- Preserve case if flag set

---

#### 3. `list_contractions() -> dict`

**Purpose:** Return all supported contractions (reference).

**Input:** None

**Output (JSON):**
```json
{
  "operation": "list_contractions",
  "total_contractions": 187,
  "contractions": {
    "don't": "do not",
    "I'll": "I will",
    "can't": "cannot",
    "won't": "will not",
    "That's": "That is",
    "I've": "I have",
    "we're": "we are",
    "you'd": "you would",
    "they've": "they have",
    "shouldn't": "should not",
    "I'm": "I am",
    "he's": "he is",
    "she'll": "she will"
  }
}
```

**Behavior:**
- Query the `contractions` library for full dictionary
- Return all supported contractions (187 common English contractions)
- Useful for validation and reference

---

### CLI Interface (in `cli.py`)

```bash
# Expand contractions in text
echo "I don't think I'll go. That's fine." \
  | python -m tools.contractions expand_contractions

# Expand single word
echo "don't" | python -m tools.contractions expand_word

# List all supported contractions
python -m tools.contractions list_contractions

# With case preservation disabled
echo "I DON'T THINK I'LL GO." \
  | python -m tools.contractions expand_contractions --preserve_case false
```

**Exit codes:**
- `0` → success
- `1` → invalid input (ValueError)
- `2` → internal error (RuntimeError)

---

### Schema (in `contractions_schema.py`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class ContractionInstance:
    contraction: str
    expansion: str
    position: int  # word position in text

@dataclass
class ExpandResult:
    operation: str
    preserve_case: bool
    original_text: str
    expanded_text: str
    contractions_found: int
    contractions_list: List[ContractionInstance]

@dataclass
class ExpandWordResult:
    operation: str
    word: str
    is_contraction: bool
    expanded: str
    case_preserved: bool = True

@dataclass
class ContractionDict:
    operation: str
    total_contractions: int
    contractions: Dict[str, str]
```

---

## Supported Contractions (Sample)

The `contractions` library supports 187+ English contractions including:

**Common:**
- I'm, I've, I'll, I'd
- don't, doesn't, didn't
- can't, couldn't, won't, wouldn't
- should've, would've, could've
- they're, we're, you're
- that's, what's, who's
- it's, there's, here's

**Possessives:**
- John's, Mary's, the dog's
- Handled transparently

**Negations:**
- n't (not), 'll (will), 'd (would/had)
- Crucial for negation_detector accuracy

---

## Error Handling

**Unified error taxonomy:**
- `FileNotFoundError` — not applicable
- `ValueError` — text is None/empty, invalid word
- `RuntimeError` — contraction library error (should be rare)
- `IOError` — not applicable

**Logging:**
- Use `structured_logger.get_event_logger("contractions")`
- Events: `expansion_started`, `expansion_complete`, `expansion_failed`
- Metadata: text_length, contractions_found, case_preserved, execution_time_ms

---

## Test Cases

### Happy Path
1. Simple contractions: "don't" → "do not"
2. Multiple contractions: "I don't think I'll go" → "I do not think I will go"
3. Case preservation: "DON'T" → "DO NOT"
4. Case preservation off: "DON'T" → "do not" (or preserve as "DO NOT")
5. Possessives: "John's book" → "John is book" (correct behavior per library)
6. Negations: "n't" in "don't" detected and expanded
7. Mixed contractions: "I'm I'll I'd I've" all expanded
8. Single word expansion: "won't" → "will not"
9. Non-contraction word: "hello" → "hello" (unchanged)
10. Empty expansion list: "hello world" → no contractions found

### Edge Cases
11. Already expanded: "do not" → "do not" (no change)
12. Very long text (1000+ words) → all contractions expanded
13. Text with punctuation: "don't, can't, won't" → all expanded
14. Contractions at sentence start: "Don't go" → "Do not go"
15. Contractions at sentence end: "I think not" (if contraction) → expanded
16. Repeated contractions: "I'll I'll I'll" → all expanded
17. Uppercase text: "I'LL NEVER CAN'T" → properly expanded with case
18. Mixed case: "I'Ll" (weird) → best-effort expansion
19. Contraction with apostrophe variations: straight vs curly quotes
20. Unicode apostrophes: handle correctly

### Error Cases
21. Text is None → `ValueError`
22. Text is empty string → `ValueError` (or handle gracefully)
23. Contraction library failure (rare) → `RuntimeError`
24. Word is None → `ValueError`
25. Invalid word type (number) → handle or `ValueError`

### CLI Behavior
26. CLI exit code 0 on success
27. CLI exit code 1 on ValueError
28. CLI exit code 2 on RuntimeError
29. CLI reads from stdin and outputs JSON
30. CLI with --preserve_case flag works

---

## Non-Goals (Explicitly Out of Scope)

- Other languages (French, Spanish, etc.)
- Slang or non-standard contractions
- Custom user-defined contractions
- Inverse operation (expansion → contraction)
- Speech patterns or dialect-specific contractions

---

## Implementation Notes

### Using the `contractions` Library

The `contractions` package provides a simple API:
```python
import contractions

# Expand a single word
expanded = contractions.fix("don't")  # "do not"

# Check if it's a contraction
is_contraction = "don't" in contractions.CONTRACTION_MAP
```

### Case Preservation Strategy

The library handles case preservation. For text like "DON'T", it expands to "DO NOT" (matching case). For "Don't", it expands to "Do not" (first-letter capitalization). Respect the library's behavior; don't override unless explicitly needed.

### Position Tracking

To track positions of contractions, tokenize the text first (using existing tokenizer) and check each token against the contraction dictionary. This gives accurate positions even with punctuation.

---

## Success Criteria

- ✅ All 30 test cases pass (manually verified with terminal output)
- ✅ CLI exit codes correct (0, 1, 2)
- ✅ Contractions expanded correctly (uses `contractions` library)
- ✅ Case preserved (original casing maintained)
- ✅ All 187+ contractions supported
- ✅ Position tracking accurate
- ✅ Errors logged via structured_logger with context
- ✅ README documents all functions and examples
- ✅ Works as preprocessing step for negation_detector (tested by negation tool)

---

**Last updated:** 2026-07-14  
**Prepared by:** Claude  
**Status:** Ready for Hermes build
