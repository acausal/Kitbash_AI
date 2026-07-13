# stage2_normalization

Post-extraction text cleanup (Stage 2 of the Document Preprocessing Pipeline).
Takes Stage 1 dispatcher/extractor output and normalizes it: line-ending
normalization (`\r\n`/`\r` → `\n`), blank-line collapse (max 2 consecutive),
leading/trailing trim, and exact-match duplicate-line removal (first occurrence
kept). No fuzzy matching, boilerplate detection, or format-specific rules — those
are v2+. Used as a standalone CLI or library import by downstream normalization /
Dream Bucket shaping. Logs via `structured_logger.py` when available.

Usage: `python -m tools.stage2_normalization input.txt [-o cleaned.txt]`
Library: `from tools.stage2_normalization import normalize_text`
