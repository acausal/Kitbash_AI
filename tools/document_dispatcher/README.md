# document_dispatcher

Single entry point for document ingestion (Stage 1 of the Document
Preprocessing Pipeline). Detects a document's format from its extension,
routes it to the matching extractor (txt/markdown/html/json/docx/rtf/odt/epub
per `SPEC-document_extractors.md`, plus the grandfathered `pdf_to_markdown`),
and writes the extracted text. Thin routing layer — all extraction logic lives
in the format-specific modules.

Optionally chains Stage 2 (`stage2_normalization`): pass `--normalize` to
whitespace-collapse and exact-dedup the extracted text. Default OFF so raw
extractor output is preserved unless requested. Logs via `structured_logger.py`
when available.

Usage: `python -m tools.document_dispatcher input.pdf [-o out.md] [--normalize]`
Library: `from tools.document_dispatcher import extract_document`
