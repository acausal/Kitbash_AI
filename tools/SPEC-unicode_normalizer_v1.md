# SPEC: Unicode Normalizer v1

**Module:** `tools/unicode_normalizer/`  
**Status:** Ready for build  
**Dependencies:** `anyascii` (PyPI, zero-dependency)  
**Priority:** High (text pipeline completion; prevents mojibake in cartridge indexing; pairs with Stage 2 Normalization)

---

## Overview

Deterministically normalize Unicode text to clean ASCII by transliterating accented characters, emoji, non-Latin scripts, and other exotic symbols. Eliminates mojibake (garbled text from encoding mismatches) and ensures consistent, reproducible text canonicalization.

**Design principle:** One-way, deterministic mapping from Unicode → ASCII. No reversibility needed. Uses `anyascii` library (Aho-Corasick based, deterministic, zero external dependencies).

**Use case:** "Ingest RSS feed with emoji and smart quotes; normalize to ASCII before indexing into cartridge system. Same text, always produces same output."

---

## Scope

### In Scope ✓
- Transliterate accented Latin characters: "café" → "cafe", "naïve" → "naive"
- Convert smart quotes/dashes: `"hello"` → `"hello"`, `—` → `-`
- Handle emoji: `😀` → `smiley face`, `🚀` → `rocket`
- Convert non-Latin scripts to ASCII approximations: "Москва" → "Moskva", "北京" → "Bei Jing"
- Preserve ASCII alphanumeric and basic punctuation
- Deterministic output (same input always produces same output)
- Configurable strictness: preserve-unknown vs. strip-unknown
- Output format: plain text (JSON wrapper with metadata)
- Handle edge cases: control characters, null bytes, mixed-script text

### Out of Scope ✗
- Language-aware transliteration (e.g., Chinese pinyin romanization customization)
- Phonetic matching or soundex
- Reversible transliteration (cannot recover original Unicode)
- Custom mapping tables (use anyascii defaults only)
- Case conversion (handled by other tools)
- Unicode normalization forms (NFC/NFD/NFKC/NFKD) — out of scope for v1

---

## Module Structure

```
tools/unicode_normalizer/
  __init__.py                    # exports main functions
  core.py                        # implementation logic (anyascii wrapper)
  cli.py                         # argparse CLI
  normalizer_schema.py           # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts).

#### 1. `normalize_text(text: str, preserve_unknown: bool = True) -> dict`

**Purpose:** Normalize Unicode text to ASCII.

**Input:**
- `text` (str): Unicode text to normalize (any encoding, any script)
- `preserve_unknown` (bool): If True, preserve characters with no ASCII mapping; if False, strip them (default: True)

**Output (JSON):**
```json
{
  "original": "Москва café 😀 — smart \"quotes\"",
  "normalized": "Moskva cafe smiley face - smart \"quotes\"",
  "changed": true,
  "char_count": {
    "original": 45,
    "normalized": 42
  },
  "mojibake_detected": false,
  "script_types_detected": ["Cyrillic", "Latin", "Emoji", "Punctuation"],
  "preserve_unknown_mode": true
}
```

**Behavior:**
- Accented chars → base char: "é" → "e", "ñ" → "n", "ü" → "u"
- Emoji → descriptive text: "😀" → "smiley face", "🚀" → "rocket"
- Smart quotes → ASCII quotes: `"` → `"`, `'` → `'`
- Dashes → hyphen: `—` → `-`, `–` → `-`
- Non-Latin scripts → approximation: "北京" → "Bei Jing", "Москва" → "Moskva"
- If `preserve_unknown=True`: unmappable chars (rare private use) kept as-is
- If `preserve_unknown=False`: unmappable chars stripped
- Null bytes and control chars (except newline/tab) removed
- Multiple spaces collapsed to single space (optional; see Config section)

**Error handling:**
- `ValueError` if text is not a valid string
- `RuntimeError` if anyascii library fails (should be rare/impossible)

**Determinism guarantee:**
- Same input (byte-for-byte) → same output, always
- No randomness; no file I/O; no external state

---

#### 2. `normalize_file(input_path: str, output_path: str, preserve_unknown: bool = True) -> dict`

**Purpose:** Normalize Unicode text from file, write to output file.

**Input:**
- `input_path` (str): Path to input text file
- `output_path` (str): Path to output file (created/overwritten)
- `preserve_unknown` (bool): Preservation mode (default: True)

**Output (JSON):**
```json
{
  "input_path": "inbox/external/raw_feed.txt",
  "output_path": "workspace/feed_normalized.txt",
  "bytes_read": 12345,
  "bytes_written": 12100,
  "lines_processed": 156,
  "normalized": true,
  "mojibake_detected": false,
  "script_types_detected": ["Latin", "Cyrillic", "Emoji"],
  "processing_time_ms": 45
}
```

**Behavior:**
- Read file as UTF-8 (fail if encoding error; user should pre-normalize if broken)
- Normalize each line independently (preserve line structure)
- Write output as UTF-8
- Return counts and metadata

**Error handling:**
- `FileNotFoundError` if input_path doesn't exist
- `IOError` if output_path not writable
- `ValueError` if input file is not valid UTF-8

---

#### 3. `detect_mojibake(text: str) -> dict`

**Purpose:** Detect likely mojibake (garbled text from encoding mismatch).

**Input:**
- `text` (str): Text to analyze

**Output (JSON):**
```json
{
  "original": "Ð¼Ð¾Ð¶Ð±Ð°Ðº",
  "mojibake_detected": true,
  "confidence": 0.87,
  "likely_source_encoding": "UTF-8 decoded as Latin-1",
  "analysis": {
    "high_ratio_of_unusual_control_sequences": true,
    "unreasonable_byte_patterns": true,
    "script_mixing_suspicious": false
  },
  "suggested_fix": "normalize_text(text)"
}
```

**Behavior:**
- Analyze byte patterns for telltale mojibake signatures
- High confidence if: unusual control sequences (U+FFFD replacement char), improbable char combinations, invalid UTF-8 sequences misinterpreted
- Return confidence score (0.0–1.0) and likely source encoding
- Suggest `normalize_text()` as fix if mojibake detected

**Heuristics:**
- Presence of U+FFFD (replacement char) → high confidence
- Sequences like "Ð¼Ð¾Ð¶" (UTF-8 bytes read as Latin-1) → pattern match
- Unusual control char density → flag
- Mixed-script text without clear boundaries → suspicious (but not definitive)

**Error handling:**
- `ValueError` if text not a string

---

### CLI Interface (in `cli.py`)

```bash
# Normalize a string (stdin or arg)
python -m tools.unicode_normalizer normalize "Москва café 😀"
python -m tools.unicode_normalizer normalize < input.txt

# Normalize file
python -m tools.unicode_normalizer normalize-file inbox/external/feed.txt workspace/feed_clean.txt

# Detect mojibake
python -m tools.unicode_normalizer detect-mojibake "Ð¼Ð¾Ð¶Ð±Ð°Ðº"

# Batch normalize (read JSON array, normalize each)
python -m tools.unicode_normalizer batch < texts.jsonl
```

**Output:** JSON to stdout (one object per line for batch; one per command for single)

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input)
- `2`: RuntimeError (I/O or library error)

---

## Configuration

**No configuration file needed.** Tool is zero-config; uses anyascii defaults.

**Optional future (v1.1):**
- Custom mapping tables (if user wants custom transliteration rules)
- Script-specific strategies (e.g., CJK pinyin mode)

---

## Data Flow Example

```
Input (RSS feed with emoji + Cyrillic + smart quotes):
  "🚀 Москва запуск — "smart quotes""

↓ unicode_normalizer.normalize_text()

Output:
  {
    "original": "🚀 Москва запуск — "smart quotes"",
    "normalized": "rocket Moskva zapusk - \"smart quotes\"",
    "changed": true,
    "script_types_detected": ["Emoji", "Cyrillic", "Punctuation", "Latin"]
  }

↓ (feed normalized, safe for cartridge indexing)

Cartridge system receives:
  "rocket Moskva zapusk - \"smart quotes\""
  (ASCII-safe, deterministic, indexed consistently)
```

---

## Testing Strategy

### Test Cases (should be straightforward)

1. **Accented Latin:** "Café naïve Zürich" → "Cafe naive Zurich"
2. **Smart quotes:** `"hello"` → `"hello"`
3. **Emoji:** "🚀 🎉 😀" → "rocket party smiley face"
4. **Non-Latin scripts:**
   - Cyrillic: "Москва" → "Moskva"
   - CJK: "北京" → "Bei Jing"
   - Greek: "Αθήνα" → "Athena"
5. **Dashes:** "em—dash en–dash hyphen-case" → "em-dash en-dash hyphen-case"
6. **Mixed:** "Москва café 😀" → "Moskva cafe smiley face"
7. **Edge cases:**
   - Empty string → empty string
   - ASCII-only → unchanged
   - Null bytes → stripped
   - Unicode normalization form handling (if already NFC vs. NFD)
8. **Mojibake detection:**
   - UTF-8 misread as Latin-1: "Ð¼Ð¾Ð¶Ð±Ð°Ðº" → `mojibake_detected: true`
   - Valid text: "café" → `mojibake_detected: false`

### Example Test File (TEST-unicode_normalizer_examples.txt)

```
# Input → Expected Output

Café → Cafe
Москва → Moskva
🚀 → rocket
— → -
"smart quotes" → "smart quotes"
北京 запуск 😀 → Bei Jing zapusk smiley face
```

---

## Safety & Validation

**Filesystem:**
- If processing files, use `tools/filesystem_access/` (no direct `open()`)
- Input from `inbox/external/` (quarantine)
- Output to `workspace/` (after validation)

**Error handling:**
- Invalid UTF-8 → fail-loud (tell user file encoding is broken)
- Preserve-unknown mode by default (safer; user can choose strip if needed)

**Reproducibility:**
- Same input (byte-for-byte) → same output, always
- No seeded randomness; deterministic library

---

## Integration Points

**Upstream (provides input):**
- Document extractors (raw text from PDFs, emails, etc.)
- RSS feed fetcher (external/quarantine)
- Raw HTTP ingester

**Downstream (consumes output):**
- Stage 2 Normalization (whitespace collapse, dedup lines)
- Tokenizer (spaCy; needs clean ASCII for best accuracy)
- Cartridge indexing (grain system for consistent lookup)
- Neighborhood Projection tool (needs stable text for topology)

---

## Non-Goals

- ❌ Reversible transliteration (one-way only)
- ❌ Language detection (not a goal; anyascii is language-agnostic)
- ❌ Phonetic matching (use separate String Distance tool)
- ❌ Custom user-defined mappings (v1 uses anyascii defaults only)
- ❌ Full Unicode form normalization (NFC/NFD handled upstream if needed)

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `anyascii` | latest | Unicode → ASCII transliteration | Zero external dependencies; pure Python; deterministic |
| stdlib | — | json, argparse, sys | No additional stdlib needed |

**No GPU, no ML, no heavy assets needed.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Custom mappings** — User can specify custom char→char rules in cartridges/
2. **v1.2: Script-aware modes** — CJK pinyin romanization, Arabic diacritic handling
3. **v2.0: Bidirectional** — Reversible transliteration (if needed for specific scripts)

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem  
**Related:** TOOLS_PIPELINE_REMAINING.md, TOOL_PHILOSOPHY.md
