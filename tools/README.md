# Tools: Isolation-First Experimental Development

This directory contains Kitbash accessories—tools, skill systems, preprocessors, and utilities—that are developed *independently* of the core pipeline during exploration and data collection phases. Tools graduate to integration only after their contracts are stable and tested in isolation.

## Isolation Contract

### Allowed Imports
- `data_structures.py` (shared type definitions; read-only)
- Standard library and pip dependencies
- Each other (within tools/)
- External libraries (spaCy, Tracery, etc.)

### Forbidden Imports
- `orchestrator.py`, `query_orchestrator.py`, `query_orchestrator_*.py`
- `sleep_*` modules (sleep_orchestrator.py, sleep_consolidator.py, etc.)
- `heartbeat_service.py`, `redis_*.py`, `redis_coupling.py`
- `bitnet_engine.py`, `cartridge_engine.py`, `grain_engine.py`
- `mtr_*.py`, `MTR_*.py`
- Any module that touches the Redis bus or triggers pipeline orchestration

**Rationale:** Kitbash core is deterministic and symbol-driven. Tools explore stateful, probabilistic, or multi-stage processing without risking hidden dependencies or side effects.

### What These Tools Can Do
- Parse, transform, or validate input data
- Emit structured output (JSON, CSV, Dream Bucket–shaped objects, etc.)
- Run as standalone CLI or library imports
- Log via `structured_logger.py` (if needed for tracing)
- Read/write from disk or optional Redis connections (but not the coordinated blackboard bus)
- Fail gracefully with clear error messages

### What These Tools Cannot Do
- Call into Kitbash query, sleep, or routing logic
- Assume real-time coordination with the main pipeline
- Mutate shared state or depend on heartbeat timing
- Publish to the Redis work queue or state bus

## Current Projects

### Deterministic Companion System
**Status:** Exploratory spec phase  
**Scope:** Input sieve (spaCy/Lark) + output linting + Tracery phatic fill  
**Intended output:** Cleaned, validated text for downstream chat or logging  
**Integration target:** Post-1.0; will become a pre-processing stage before query orchestrator

### Document Preprocessing Pipeline
**Status:** Exploratory spec phase  
**Scope:** Ingest structured documents (PDF, markdown, JSON); emit Dream Bucket–shaped violation/fact objects  
**Intended output:** Cold-storage indexed cartridge material ready for sleep pipeline  
**Integration target:** Post-1.0; becomes part of the sleep input layer

## Current Tools

### pdf_to_markdown
**Status:** Implemented (Stage 1 of Document Preprocessing Pipeline)
**Scope:** Single-PDF text extraction via `pypdf`; flat, whitespace-normalized output with `--- PAGE N ---` markers. No structure inference.
**Intended output:** Cleaned text file (`.md`) for later normalization / Dream Bucket shaping.
**Integration target:** Post-1.0; feeds the sleep input layer.
**Spec:** `SPEC-pdf_to_markdown.md` · **Code:** `pdf_to_mark_down/` · **Usage:** `python -m tools.pdf_to_markdown input.pdf [-o out.md]`
(Naming note: this tool pre-dates `SPEC-document_extractors.md`; the master SPEC standard is `<format>_extractor/` + `convert_<format>_to_markdown`. The 4 below follow that standard; pdf_to_markdown is grandfathered.)

### document_dispatcher
**Status:** Implemented (primary ingestion entry point; Stage 1)
**Scope:** Detects format from extension, routes to the matching extractor (the 8 `<format>_extractor` tools + grandfathered `pdf_to_markdown`), writes extracted text. Thin routing layer only. Optional `--normalize` flag chains Stage 2 (`stage2_normalization`) on the extracted output.
**Intended output:** Extracted text file (`.md`); normalized if `--normalize` passed.
**Integration target:** Stage 1 → feeds Stage 2 or downstream storage.
**Spec:** `SPEC-document_dispatcher.md` · **Code:** `document_dispatcher/` · **Usage:** `python -m tools.document_dispatcher input.pdf [-o out.md] [--normalize]`

### tokenizer
**Status:** Implemented (input sieve / preprocessing; spaCy)
**Scope:** Generic English tokenization (v1) via spaCy `en_core_web_sm`. Optional lemmatization + stop-word removal. Returns `Token` objects (text, lemma, POS, is_stop/is_punct/is_space, idx, doc_idx). Slang/abbrev/spelling/multilang deferred to v2+.
**Intended output:** `Token` list (library) or JSON `{tokens, token_count, stop_word_count}` (CLI).
**Integration target:** feeds input-sieve query handling + document preprocessing.
**Spec:** `SPEC-tokenizer_v1.md` · **Code:** `tokenizer/` · **Usage:** `python -m tools.tokenizer input.txt [--lemma] [--remove-stop]`
(Requires `spacy` + `en_core_web_sm`; in the Kitbash `.venv` prefix invocations with `PYTHONPATH= ` to avoid the leaked agent-venv shadowing pydantic.)

### negation_detector
**Status:** Implemented (input sieve / preprocessing; spaCy)
**Scope:** Detects negation markers (`not`, `no`, `never`, `neither`, `nor`, + split contractions via lemma `not`) and flags tokens within a distance `window` (default 5) as `is_negated`. v1: hardcoded list + fixed window; scope analysis / multi-word / double-negatives deferred to v2+.
**Intended output:** `Token` list with `is_negated` (library) or JSON `{tokens, token_count, negated_count, negation_markers}` (CLI).
**Integration target:** chains after tokenizer / feeds input-sieve + document preprocessing.
**Spec:** `SPEC-negation_detector_v1.md` · **Code:** `negation_detector/` · **Usage:** `python -m tools.negation_detector input.txt [--window N]`
(Reuses `spacy` + `en_core_web_sm`; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### ner
**Status:** Implemented (input sieve / preprocessing; spaCy)
**Scope:** Named entity recognition via spaCy `en_core_web_sm` default types (PERSON, ORG, GPE, DATE, MONEY, ...). Optional label filtering. Returns `Entity` objects (text, label, start, end, doc_idx). Fine-tuning / custom types / entity linking / relationships / confidence deferred to v2+.
**Intended output:** `Entity` list (library) or JSON `{entities, entity_count, label_counts}` (CLI).
**Integration target:** input-sieve query handling + document preprocessing.
**Spec:** `SPEC-ner_v1.md` · **Code:** `ner/` · **Usage:** `python -m tools.ner input.txt [--labels PERSON,ORG] [--output out.json]`
(Reuses `spacy` + `en_core_web_sm`; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### svo
**Status:** Implemented (input sieve / preprocessing; spaCy)
**Scope:** Subject-Verb-Object extraction via spaCy dependency parse (`en_core_web_sm`). One SVO per main clause; head-word subject/object (nsubj/nsubjpass, dobj/iobj/attr). Sentences without a main verb skipped. Full-span phrases / subordinate clauses / SRL deferred to v2+.
**Intended output:** `SVO` list (library) or JSON `{svos, svo_count, with_subject, with_object}` (CLI).
**Integration target:** input-sieve query handling + document preprocessing (complements NER + negation_detector).
**Spec:** `SPEC-svo_v1.md` · **Code:** `svo/` · **Usage:** `python -m tools.svo input.txt [-o out.json]`
(Reuses `spacy` + `en_core_web_sm`; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### structured_validator
**Status:** Implemented (input sieve / preprocessing; Lark)
**Scope:** Generic Lark-grammar validation. `validate_input(text, grammar, grammar_start)` → `ParseResult` (success, serialized parse tree dict, error, grammar_name, input_text). Inline EBNF or `.lark` file. No built-in grammars (v1 = infrastructure; concrete grammars deferred to use cases).
**Intended output:** `ParseResult` (library) or JSON `{success, grammar_name, parse_tree, error, input_text}` (CLI). Exit 0=pass / 1=validation fail / 2=grammar/file error.
**Integration target:** optional validation stage after tokenizer/ner/svo in the input sieve.
**Spec:** `SPEC-structured_validator_v1.md` · **Code:** `structured_validator/` · **Usage:** `python -m tools.structured_validator input.txt --grammar g.lark [--output out.json]`
(Requires `lark`; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### datetime_utils
**Status:** Implemented (data plumbing; stdlib + pytz)
**Scope:** 7 functions — parse_iso8601, parse_epoch (s/ms), parse_string (strptime), format_timestamp (iso8601/unix[s|ms]/human), get_current_time, duration_between (with breakdown), timezone_offset (DST-aware). Thin wrapper over datetime + pytz; UTC-internal, seconds precision. No calendar/NL parsing (v2+).
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads JSON from stdin, writes JSON to stdout. Exit 0/1/2.
**Integration target:** data plumbing for time-series ops + log parsing.
**Spec:** `SPEC-datetime_v1.md` · **Code:** `datetime_utils/` · **Usage:** `echo '{"timestamp":"..."}' | python -m tools.datetime_utils parse_iso8601`
(Requires `pytz`; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### neighborhood_projection
**Status:** Implemented (graph plumbing; stdlib only)
**Scope:** 5 functions — project_neighborhood (BFS, depth + strength filter), project_neighborhood_bidirectional (marks in/out edges), filter_neighborhood (min_strength + min_degree), rank_neighborhood_by_weight (asc/desc), explain_path (shortest path ≤5 hops). Multiplicative path weights. Node type/cartridge DERIVED from edges (no node registry). Read-only over an edge-graph snapshot.
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads JSON from stdin, writes JSON to stdout. Exit 0/1/2.
**Integration target:** post-1.0 sleep-pipeline Tier-2 context expansion + query-time debugging.
**Spec:** `SPEC-neighborhood_projection_v1.md` · **Code:** `neighborhood_projection/` · **Usage:** `echo '{"edge_graph":{...},"seed_nodes":["fact_123"]}' | python -m tools.neighborhood_projection project_neighborhood`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### log_parser
**Status:** Implemented (trace plumbing; stdlib only)
**Scope:** 6 functions — parse_jsonl_traces (report + normalized traces), parse_json_trace, normalize_trace (required-field validation + defaults + step inference), filter_traces (AND semantics: time/session/chain_type/length/element_type/cartridge), aggregate_chains (unique sequence frequency), extract_chain_steps (consecutive transitions for n-grams). Prefixed sequence form "<type>_<id>". Lenient parse / strict validation.
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads JSON/JSONL from stdin or --input, writes stdout or --output; --filter/--aggregate chaining. Exit 0/1/2/3.
**Integration target:** prepares traces for Sequence Pattern Miner → Conditional Pattern Detector chain.
**Spec:** `SPEC-log_parser_v1.md` · **Code:** `log_parser/` · **Usage:** `cat traces.jsonl | python -m tools.log_parser parse_jsonl_traces`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### txt_extractor
**Status:** Implemented (Document Format Extractors, stdlib)
**Scope:** `.txt` → normalized text (UTF-8, Latin-1 fallback; line-endings + blank-line collapse).
**Code:** `txt_extractor/` · **Usage:** `python -m tools.txt_extractor input.txt [-o out.md]`

### markdown_extractor
**Status:** Implemented (stdlib)
**Scope:** `.md`/`.markdown` → pass-through normalization (preserves MD syntax; collapses blank lines).
**Code:** `markdown_extractor/` · **Usage:** `python -m tools.markdown_extractor input.md [-o out.md]`

### html_extractor
**Status:** Implemented (stdlib `html.parser`)
**Scope:** `.html`/`.htm` → text (skips `script`/`style`/`meta`/`head`; decodes entities).
**Code:** `html_extractor/` · **Usage:** `python -m tools.html_extractor input.html [-o out.md]`

### json_extractor
**Status:** Implemented (stdlib `json`)
**Scope:** `.json` → text from `content`/`text`/`body`/`message`/`data` fields (joined with `\n---\n`).
**Code:** `json_extractor/` · **Usage:** `python -m tools.json_extractor input.json [-o out.md]`

### docx_extractor
**Status:** Implemented (Document Format Extractors; `python-docx`)
**Scope:** `.docx` → text (paragraphs as lines; tables as `| col | col |` rows).
**Code:** `docx_extractor/` · **Usage:** `python -m tools.docx_extractor input.docx [-o out.md]`

### rtf_extractor
**Status:** Implemented (`striprtf`)
**Scope:** `.rtf` → text (control words / embedded objects stripped).
**Code:** `rtf_extractor/` · **Usage:** `python -m tools.rtf_extractor input.rtf [-o out.md]`

### odt_extractor
**Status:** Implemented (`odfpy`)
**Scope:** `.odt` → text (paragraphs via `odf.teletype.extractText`).
**Code:** `odt_extractor/` · **Usage:** `python -m tools.odt_extractor input.odt [-o out.md]`

### epub_extractor
**Status:** Implemented (`ebooklib` + stdlib HTMLParser)
**Scope:** `.epub` → text (per-chapter HTML stripped; chapters joined with `\n--- CHAPTER ---\n`).
**Code:** `epub_extractor/` · **Usage:** `python -m tools.epub_extractor input.epub [-o out.md]`

> All 8 format extractors now build on the shared contract in `SPEC-document_extractors.md`. PyPI deps (`python-docx`/`striprtf`/`odfpy`/`ebooklib`) are installed in `.venv`.

### stage2_normalization
**Status:** Implemented (Stage 2 of Document Preprocessing Pipeline)
**Scope:** Whitespace normalization (line-ending + blank-collapse max 2 + trim) and exact-match duplicate-line removal (first occurrence kept; blank lines excluded from dedup so paragraph spacing survives).
**Intended output:** Cleaned text for downstream normalization / Dream Bucket shaping.
**Integration target:** Post-1.0; consumes Stage 1 (dispatcher/extractor) output.
**Spec:** `SPEC-stage2_normalization.md` · **Code:** `stage2_normalization/` · **Usage:** `python -m tools.stage2_normalization input.txt [-o cleaned.txt]`

## Adding a New Tool

1. Create a subdirectory: `tools/<tool_name>/`
2. Include a `README.md` (one paragraph: what it does, who calls it, why it exists)
3. Include a `SPEC-<tool_name>.md` if the tool is complex (processing stages, contracts, error handling)
4. Import only what's allowed (see Allowed Imports above)
5. If it needs config, use environment variables or a local JSON file; no shared Kitbash config injection
6. Fail loud: raise exceptions clearly, don't silently degrade

## Integration Pathway (Post-1.0)

When a tool is ready to integrate:

1. **Contract review:** Does its output shape match what Kitbash needs? (Dream Bucket entry? Cartridge material? Sieve output?)
2. **Dependency audit:** Does it introduce any forbidden imports?
3. **Merge:** Move to top-level module (e.g., `companion.py`, `preprocessor.py`)
4. **Wiring:** Add to appropriate orchestrator entry point (query or sleep)
5. **Test coverage:** E2E tests in main test suite

Until then, tools live here—safe, autonomous, and free to experiment.

## Hermes Development Guidelines

When building tools in this directory:
- **Assume isolation.** You cannot reach into Kitbash core.
- **Specs first.** Write the SPEC before code; include I/O contracts and error cases.
- **Fail gracefully.** Provide clear error messages and recovery paths.
- **Log structured data.** Use `structured_logger.py` if you need operational visibility.
- **Test in isolation.** Your test suite should not require Kitbash to be running.
- **Document non-goals.** State clearly what the tool does *not* do; defer scope creep to POST_MVP_ROADMAP.md.

## Questions?

If a tool needs something from Kitbash core (a type, a utility function, a constant), ask first. We may extract it to `data_structures.py` or `__init__.py`. Don't work around the boundary—make the boundary explicit.
