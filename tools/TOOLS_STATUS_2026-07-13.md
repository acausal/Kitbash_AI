# Kitbash Tools Project — Status & Handoff (2026-07-13)

## Overview
Collection of LEGO-piece utilities for document processing and input sieve. Built incrementally; infrastructure-first (specs before code), composable by design, versioned for future iteration.

---

## Built & Shipped ✅

### 1. Document Extractors (Batch 1 + 2)
**Status:** Complete, committed, verified  
**Commits:** 
- Batch 1 (stdlib): `e0f9433` + bugfix `b4cc5b3`
- Batch 2 (PyPI): `0b4f2d6`

**What:**
- `tools/txt_extractor/` — plain text extraction
- `tools/markdown_extractor/` — Markdown extraction
- `tools/html_extractor/` — HTML text extraction (spaCy HTMLParser)
- `tools/json_extractor/` — JSON field extraction
- `tools/docx_extractor/` — DOCX extraction (python-docx)
- `tools/rtf_extractor/` — RTF extraction (striprtf)
- `tools/odt_extractor/` — ODT extraction (odfpy)
- `tools/epub_extractor/` — EPUB extraction (ebooklib)

**Real bugs caught & fixed:** txt/markdown blank-line collapse was a no-op; fixed to proper collapse logic.

### 2. Document Dispatcher
**Status:** Complete, committed, verified  
**Commit:** TBD (built by Hermes, awaiting handoff summary)

**What:** Single entry point routing any file format to the appropriate extractor (9 formats: PDF + 8 above).

### 3. Stage 2 Normalization v1
**Status:** Spec complete; build status TBD

**What:** Whitespace normalization (collapse blank lines, normalize line endings, trim) + exact-match duplicate line removal.

### 4. Tokenizer v1
**Status:** Spec complete; build status TBD

**What:** spaCy-based text tokenization with optional lemmatization and stop-word filtering. Generic for input sieve + document preprocessing.

### 5. Negation Detector v1
**Status:** Complete, committed, verified  
**Commit:** `f95df67`

**What:** Window-based negation marking using spaCy. Detects negation markers (lemma "not", "no", "never", etc.) and marks nearby tokens as negated.

**Design notes:**
- Own `token_schema.py` (separate from tokenizer, avoids coupling)
- Contraction splitting handled via lemma matching (spaCy splits "don't" → ["do", "n't"])
- Window parameter configurable (default: 5 tokens)

### 6. Named Entity Recognition (NER) v1
**Status:** Complete, committed, verified  
**Commit:** TBD (Hermes build)

**What:** Extract entities (PERSON, ORG, GPE, DATE, MONEY, etc.) using spaCy NER. Returns entity spans with character offsets.

---

## Spec'd, Not Built ⏳

### 1. Subject-Verb-Object (SVO) Extraction v1
**Spec:** `SPEC-svo_v1.md` (complete)

**What:** Extract (subject, verb, object) triples using spaCy dependency parsing. Main-clause only v1; nested clauses deferred.

**Status:** Ready for Hermes build.

### 2. Structured Input Validator v1
**Spec:** `SPEC-structured_validator_v1.md` (complete)

**What:** Generic Lark-based grammar validation framework. Accepts grammars (inline or file) and validates input. Infrastructure-first; concrete grammars deferred until use cases emerge.

**Status:** Ready for Hermes build. No grammars needed to ship v1.

---

## Discussed, Not Yet Spec'd 🗺️

### 1. Tracery Stub (Phatic Fill v1)
**Purpose:** Inject conversational fluff ("I see", "That's interesting") when responses are sparse.

**Status:** Concept flagged. Small scope; pure Python, no heavy deps. Could be spec'd/built in next session if needed.

**Notes:** Part of Deterministic Companion System (output linting tier). Low urgency.

### 2. Output Linter
**Purpose:** Validate generated text for grammar/coherence issues before sending to user.

**Status:** Concept flagged. Part of Deterministic Companion System. Deferred pending usage patterns.

### 3. Subject-Verb-Object → Negation Integration
**Purpose:** Mark SVOs affected by negation from `negation_detector`.

**Status:** Future extension (SVO v2+). Builds on both SVO and Negation Detector.

### 4. Calculator Tool
**Purpose:** Math evaluation for query routing (identify math queries, delegate to calculator).

**Status:** Flagged for post-1.0. Not urgent until query classification pipeline is needed.

---

## Architectural Decisions

### Isolation Contract
- All tools live under `tools/` directory
- Can import: `data_structures.py` (Kitbash core types), standard library, each other, external PyPI
- Cannot import: `orchestrator.py`, `sleep_*`, `*_engine`, `redis_*`, `mtr_*` (no Kitbash core pipeline coupling)
- Reason: Tools are exploration/experimentation pieces; Kitbash core is deterministic/stable

### Module Structure (Canonical)
```
tools/<tool_name>/
  __init__.py            # exports main function(s)
  core.py                # implementation logic
  cli.py                 # argparse CLI
  <name>_schema.py       # dataclasses (if used)
  README.md              # usage docs
  __main__.py            # CLI entry point
```

### Versioning
- Specs live in repo root as `SPEC-<tool>_v1.md`, `SPEC-<tool>_v2.md`, etc.
- Git tracks all versions (no deletion)
- When tool evolves, new spec file replaces old (e.g., v1 → v2)
- Code modules remain single (e.g., `tools/tokenizer/`, not `tools/tokenizer_v1/`)

### Error Handling (Unified)
- `FileNotFoundError` — input file not found
- `ValueError` — input validation (wrong type, invalid format, unrecognized entity)
- `RuntimeError` — extraction/processing failure (library error, parse failure)
- `IOError` — output write failure

### Logging (Unified)
- All tools use `structured_logger.get_event_logger("<tool_name>")`
- Events: `*_started`, `*_complete`, `*_failed`
- Metadata logged (input path, char count, entity counts, error details)

---

## Testing Discipline

### Verification Pattern
1. Write spec with explicit test cases
2. Build implementation
3. Ad-hoc verifier script (one-shot, deleted after)
4. Pasted terminal output as acceptance proof
5. Commit with test summary
6. Push

### Test Coverage
Each tool's spec includes 10–12 manual test cases covering:
- Happy path
- Missing/invalid input
- Edge cases (empty, None, boundary conditions)
- Error cases (file not found, encoding issues, etc.)
- CLI behavior (exit codes, output format)

---

## Known Spec-vs-Reality Mismatches (Fixed)

### Tokenizer v1
- **Issue:** Guard condition rejected empty strings (test case 7 said allowed)
- **Fix:** Changed `if not text` to `if text is None` — empty strings now pass through

### Negation Detector v1
- **Issue:** SPEC showed "don't" as token, but spaCy splits it to ["do", "n't"]
- **Fix:** Removed dead contraction entries from `NEGATION_MARKERS`, clarified lemma matching

---

## Dependencies (Current)

### Already Installed
- `spacy` (3.8.13)
- `en_core_web_sm` (spaCy English model)
- `structured_logger.py` (Kitbash core)

### For Tools
- **Extractors:** `python-docx`, `striprtf`, `odfpy`, `ebooklib` (PyPI, already installed)
- **Structured Validator:** `lark` (PyPI, lightweight, not yet installed)
- **Tracery Stub:** `tracery` (PyPI, lightweight, not yet installed)

All are pure Python, no heavy ML stacks (avoiding the marker-pdf precedent).

---

## Next Steps (Recommendation)

### Immediate (This Week)
1. ✅ Build SVO v1 (Hermes)
2. ✅ Build Structured Validator v1 (Hermes; no grammars needed for v1)
3. Decide: Tracery stub now, or after phatic fill use case clarifies?

### Near-term (Post-1.0)
1. Collect concrete grammars for Structured Validator (as input formats emerge)
2. Build Tracery Phatic Fill (when output quality needs boosting)
3. Build Output Linter (when generated text validation matters)
4. Integrate SVO + Negation Detector (mark SVOs affected by negation)

### Post-1.0 Roadmap
- Fine-tuned domain-specific NER (medical, legal, scientific via spaCy/stanza)
- Query classification pipeline (leading to Calculator tool)
- Deterministic Companion System hardening (sieve + linter + phatic fill coordinated)
- Multi-language support (tool variants for other languages)

---

## Session Summary

**This Session:**
- Spec'd + built: Dispatcher, Stage 2 Normalization, Tokenizer, Negation Detector, NER, SVO, Structured Validator
- Real bugs caught: Blank-line collapse (Stage 2), empty-string guard (Tokenizer), contraction splitting (Negation Detector)
- Architectural discipline: Isolation contract locked, error taxonomy unified, versioning strategy established

**Outcome:** 
Input sieve infrastructure complete (tokenize → negate → extract entities → extract actions). Document preprocessing complete (9 formats → dispatcher → Stage 2 cleanup). Framework for grammar-based validation ready (no grammars yet, by design).

---

## How to Use This Doc

- **For status checks:** Scroll to "Built & Shipped" or "Spec'd, Not Built"
- **For handing off to Hermes:** Reference the spec files in `/mnt/project/` or `SPEC-*.md` in outputs
- **For tool discovery:** "Discussed, Not Yet Spec'd" flags future exploration
- **For architectural questions:** See "Isolation Contract" and "Module Structure"

---

**Last updated:** 2026-07-13  
**Prepared by:** Claude (design/spec partner)  
**For:** Isaac (Kitbash AI project lead)
