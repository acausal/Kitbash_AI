# SPEC: Stage 2 Normalization v1

## Purpose
Post-extraction text cleanup: normalize whitespace and remove exact-match duplicate lines. This is the first version of a multi-stage preprocessing pipeline; v2+ will add pattern-based boilerplate detection, format-specific rules, etc. For now: whitespace collapse + dedup.

## Scope

### In Scope
- Accept extracted text from Stage 1 (dispatcher output)
- Normalize line endings (`\r\n` → `\n`)
- Collapse multiple blank lines (max 2 consecutive newlines)
- Trim leading/trailing whitespace
- Remove exact-match duplicate lines (keep first occurrence, strip later duplicates)
- Return cleaned text
- CLI entry point: `python -m tools.stage2_normalization <input.txt> [--output <output.txt>]`
- Library API: `normalize_text(text: str) -> str`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Fuzzy line matching (similar but not identical lines)
- Pattern-based boilerplate detection (regex, heuristics)
- Format-specific rules (PDF vs HTML vs DOCX)
- Metadata return (lines removed, etc.—saved for v2)
- Integration with Stage 1 or downstream storage
- Language-aware processing (stemming, lemmatization)

## API Contract

### Library API
```python
from tools.stage2_normalization import normalize_text

cleaned = normalize_text(extracted_text)
```

**Signature:**
```python
def normalize_text(text: str) -> str:
    """
    Normalize whitespace and remove exact-match duplicate lines.
    
    Args:
        text: Raw extracted text from Stage 1
    
    Returns:
        Cleaned text (normalized whitespace, deduped lines)
    
    Raises:
        ValueError: Text is None or not a string
    """
```

### CLI
```bash
python -m tools.stage2_normalization input.txt
python -m tools.stage2_normalization input.txt --output cleaned.txt
python -m tools.stage2_normalization input.txt -o cleaned.txt
```

**Behavior:**
- Read input text (from file or stdin if not specified)
- Normalize and deduplicate
- Write to output (or stdout)
- Exit code 0 on success
- Exit code 1 on failure (with stderr message)
- Print summary to stdout: `Normalized <input> → <output> (<N> chars → <M> chars, <K> duplicates removed)`

### Error Handling
- `FileNotFoundError`: input file does not exist
- `ValueError`: input is None, empty string, or not a string
- `IOError`: output cannot be written

## Implementation Notes

### Whitespace Normalization
1. **Line ending normalization:**
   ```python
   text = text.replace('\r\n', '\n').replace('\r', '\n')
   ```

2. **Collapse multiple blank lines:**
   - Split into lines
   - Iterate through lines; keep non-empty lines and single blank lines
   - Collapse sequences of 3+ consecutive newlines to 2 newlines
   - Pseudocode:
     ```python
     lines = text.split('\n')
     cleaned_lines = []
     blank_count = 0
     for line in lines:
         if line.strip() == '':
             blank_count += 1
             if blank_count <= 2:  # Keep max 2 consecutive blanks
                 cleaned_lines.append(line)
         else:
             blank_count = 0
             cleaned_lines.append(line)
     text = '\n'.join(cleaned_lines)
     ```

3. **Trim leading/trailing whitespace:**
   ```python
   text = text.strip()
   ```

### Exact-Match Duplicate Line Removal
1. Split into lines
2. Track seen lines (use a set for O(1) lookup)
3. Iterate through lines; keep only first occurrence of each unique line
4. Rejoin
   ```python
   lines = text.split('\n')
   seen = set()
   deduped_lines = []
   duplicate_count = 0
   for line in lines:
       if line not in seen:
           seen.add(line)
           deduped_lines.append(line)
       else:
           duplicate_count += 1
   text = '\n'.join(deduped_lines)
   return text, duplicate_count
   ```

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("stage2_normalization")

logger.log(event_type="normalization_started", data={"source": input_path, "char_count": len(text)})
logger.log(event_type="normalization_complete", data={
    "source": input_path, 
    "dest": output_path, 
    "char_count_before": len_before, 
    "char_count_after": len_after,
    "duplicates_removed": dup_count
})
logger.error(event_type="normalization_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Happy path:** Input with excess blank lines + duplicates → verify output is normalized and deduped
2. **Whitespace collapse:** Input with 5 consecutive newlines → verify collapsed to 2
3. **Exact duplicates:** Input with repeated lines → verify only first occurrence kept
4. **Already clean:** Input with no issues → verify unchanged (or whitespace trimmed)
5. **Empty input:** Empty string → verify returns empty string (not an error)
6. **Single line:** Single line of text → verify unchanged
7. **Mixed line endings:** Input with `\r\n` and `\n` → verify all normalized to `\n`
8. **Missing file:** Nonexistent input path → verify `FileNotFoundError`
9. **Non-string input:** Pass None or non-string → verify `ValueError`
10. **Permission denied:** Attempt to write to read-only dir → verify `IOError`

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works with file input and output
- Whitespace normalization correct (blank-line collapse, line-ending normalization, trimming)
- Exact-duplicate removal correct (first occurrence kept, later duplicates removed)
- Error cases raise appropriate exceptions
- Output summary is accurate (char counts, duplicate count)
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/stage2_normalization/
  __init__.py          # exports normalize_text()
  cli.py               # argparse CLI
  README.md            # usage docs
```

## Future Extensions (v2+)
- Fuzzy line matching (similar but not identical)
- Pattern-based boilerplate detection (regex heuristics)
- Format-specific rules (PDF headers, HTML nav text, etc.)
- Metadata return (`{"text": "...", "lines_removed": 42, ...}`)
- Language-aware processing
- spaCy/TextaCy integration for sentence segmentation

## Done When
- `tools/stage2_normalization/__init__.py` exports `normalize_text()`
- `tools/stage2_normalization/cli.py` implements CLI via argparse
- `tools/stage2_normalization/README.md` documents usage
- All 10 manual test cases pass with pasted output
- `tools/README.md` updated to list stage2_normalization
