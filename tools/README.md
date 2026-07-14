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

### sequence_pattern_miner
**Status:** Implemented (pattern mining; stdlib only)
**Scope:** 5 functions — extract_ngrams (sliding-window n-grams, freq rank, trace-level chain_filter fact_only/grain_only/mixed), extract_ngrams_by_length (n=min..max in one call), filter_sequences (min/max freq, re-ranked), rank_sequences_by_element_type (group by fact→fact/grain→grain/mixed), sequences_to_markov_transitions (bigrams → per-source transition probabilities summing to 1.0). Prefixed "<type>_<id>" elements. Exact counting, no stats (v1).
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads JSON from stdin, writes stdout; typed flags override payload. Exit 0/1/2.
**Integration target:** consumes log_parser output; feeds sleep Tier-2 meta-learning + Markov Chain tool.
**Spec:** `SPEC-sequence_pattern_miner_v1.md` · **Code:** `sequence_pattern_miner/` · **Usage:** `echo '{"traces":[...]}' | python -m tools.sequence_pattern_miner extract_ngrams --n 2`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### text_search
**Status:** Implemented (data plumbing; stdlib only)
**Scope:** 5 functions — search_text / search_lines (per-line regex, 1-indexed, context_before/after, inverse), search_and_extract (capture groups group_0..n), count_matches (counts + match_density), replace_matches (backreferences, count_limit, change log). Flags: case_insensitive (re.IGNORECASE), multiline (re.DOTALL), verbose (re.VERBOSE). Thin stdlib `re` wrapper.
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads raw text from stdin, flags via argparse, writes stdout. Exit 0/1/2.
**Integration target:** foundational search over logs, cartridge text, traces, any indexed content.
**Spec:** `SPEC-text_search_v1.md` · **Code:** `text_search/` · **Usage:** `echo "..." | python -m tools.text_search search_text --pattern "photo"`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### line_filtering
**Status:** Implemented (data plumbing; stdlib only)
**Scope:** 7 functions — sort_lines (asc/desc, case-insensitive), deduplicate_lines (preserve-order via dict.fromkeys, optional sort), count_line_frequency (Counter + percent, freq/lexicographic sort, distribution stats), filter_by_frequency (keep all occurrences in [min,max] range), unique_lines (appear-exactly-once), head_tail_lines (n, tail), reverse_lines. No whitespace trim by default (preserve as-is).
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads raw text from stdin, writes stdout. Exit 0/1/2.
**Integration target:** pairs with text_search in text-processing chains.
**Spec:** `SPEC-line_filtering_v1.md` · **Code:** `line_filtering/` · **Usage:** `echo -e "a\nb\nc" | python -m tools.line_filtering sort_lines`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### json_query_filter
**Status:** Implemented (data plumbing; stdlib only)
**Scope:** 5 functions — query_json (recursive-descent path DSL: `.field.nested`, `[i]`, `[*]`, `[s:e]`, `[?filter]`, `// default`, `.{a,b}`, `| type|length`), filter_json_array (`?field op value`, op∈== != > <), extract_fields (object/array subset), flatten_json (separator, max_depth; arrays kept as values), validate_schema (required + types; extra fields allowed). Missing/null/type-mismatch -> null+found=false (graceful).
**Intended output:** JSON-serializable dicts (library + CLI); CLI reads JSON from stdin. Exit 0/1/2.
**Integration target:** pairs with line_filtering/text_search for data plumbing.
**Spec:** `SPEC-json_query_filter_v1.md` · **Code:** `json_query_filter/` (+ `query_parser.py`, 7 files) · **Usage:** `echo '{"u":{"n":"A"}}' | python -m tools.json_query_filter query_json --query .u.n`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### conditional_pattern_detector
**Status:** Implemented (Tier 2 meta-learning; stdlib only)
**Scope:** 5 functions — detect_conditional_patterns (auto-conditions: chain_length, element_presence, element_type_distribution, element_count, traversal_type_pattern; outcomes: element_type_distribution/sequence, next_element_type, traversal_type_dominance; metrics support/confidence/lift/inverse_confidence), detect_seeded_patterns, extract_decision_trees (entropy/info-gain, target FIXED = `grain_present_in_chain`), filter_patterns (AND thresholds), rank_patterns_by_metric (confidence/lift/support). Traces = log_parser normalized objects (skip empty/missing chain). SKIPPED (post-1.0, documented in `skipped_types`): conditions cartridge_crossing/session_consistency, outcomes success_rate/cartridge_distribution (log_parser lacks per-step confidence/success). lift guard: baseline=1.0 -> 1.0.
**Intended output:** JSON-serializable dicts (library + CLI). Exit 0/1/2.
**Integration target:** consumes log_parser traces; feeds sleep Tier 2 meta-learning.
**Spec:** `SPEC-conditional_pattern_detector_v1.md` · **Code:** `conditional_pattern_detector/` (6 files) · **Usage:** `echo '{"traces":[...]}' | python -m tools.conditional_pattern_detector detect_conditional_patterns --min_support 2`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### filesystem_access
**Status:** Implemented (safety-critical Airlock; stdlib only)
**Scope:** 6 functions — read_file, write_file (atomic temp→fsync→os.replace; modes w/a/x), delete_file, list_directory (non-recursive/recursive, metadata), file_exists, get_file_metadata. path_validator: rejects absolute paths, traversal (resolve-outside-root), symlinks, non-allowed dirs, per-op permission (read/write/delete per allowed_paths). Boundary violations -> ValueError (CLI 1); missing -> FileNotFoundError (CLI 2); IO -> RuntimeError/IOError (CLI 3). Audit JSONL appended per op (best-effort). config_loader falls back to bundled default_config.json (does NOT write to cartridges/ — tracked/sensitive; deploy real config there to use it).
**Intended output:** JSON-serializable dicts (library + CLI). Exit 0/1/2/3.
**Integration target:** All tool I/O should flow through it (unblocks I/O-heavy tools).
**Spec:** `SPEC-filesystem_access_v1.md` · **Code:** `filesystem_access/` (+ `path_validator.py`, `config_loader.py`, `default_config.json`, 9 files) · **Usage:** `echo '{"k":1}' | python -m tools.filesystem_access write_file --path "workspace/out.json"`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### contractions
**Status:** Implemented (preprocessing for tokenizer/negation_detector; depends on `contractions` PyPI lib v0.1.73 + transitives textsearch/anyascii/pyahocorasick — first tools pkg needing a 3rd-party dep; installed in .venv). 3 functions: expand_contractions (text + per-contraction word-positions), expand_word (single token + is_contraction), list_contractions (791-entry merged dict: contractions_dict+leftovers_dict+slang_dict; SPEC's `contractions.CONTRACTION_MAP` does NOT exist in v0.1.73). Case preserved via library (don't→do not, DON'T→DO NOT). Possessives NOT expanded (library behavior; SPEC case-5 example stale). Errors: ValueError→1 (None/empty), RuntimeError→2 (lib failure). Exit 0/1/2.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-contractions_v1.md` · **Code:** `contractions/` (6 files) · **Usage:** `echo "I don't think I'll go." | python -m tools.contractions expand_contractions`
(Requires the `contractions` dep; invoke via Kitbash `.venv` with `PYTHONPATH= `.)

### csv_operations
**Status:** Implemented (foundational data plumbing; stdlib only). 6 functions: parse_csv (Sniffer dialect detect + BOM strip + headerless→col_N keys + NULL-token norm), filter_rows (== != > < >= <= regex; numeric ops with string fallback), select_columns (keep/exclude, order-preserving), sort_rows (stable; numeric validates), unique_values (counts sorted by count desc), csv_stats (type inference text/numeric + min/max + samples). Errors: ValueError→1, FileNotFoundError→2, IOError/RuntimeError→3. Exit 0/1/2/3.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-csv_operations_v1.md` · **Code:** `csv_operations/` (+ `csv_parser.py`, `filters.py`, 8 files) · **Usage:** `echo "name,age\nAlice,30" | python -m tools.csv_operations parse_csv`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### unicode_normalizer
**Status:** Implemented (text pipeline completion; `anyascii` dep, already in `.venv` via `contractions`). 3 functions: normalize_text (deterministic Unicode→ASCII, preserve/strip-unknown, control-char strip, space-collapse, script classifier), normalize_file (line-by-line UTF-8 in→out with counts), detect_mojibake (heuristic: U+FFFD / Latin-1-misread sequences / script-mixing). Errors: ValueError→1, FileNotFoundError/OSError/RuntimeError→2. Exit 0/1/2. **Spec deviations:** emoji→`:rocket:`/`:grinning:`/`:tada:` (not "rocket"/"smiley face"/"party"), `北京`→`BeiJing` (no space), `Αθήνα`→`Athina`; TEST doc's `−` (U+2212) dash glitch → actual `-`. Honors anyascii defaults (custom maps out of scope).
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-unicode_normalizer_v1.md` · **Code:** `unicode_normalizer/` (6 files) · **Usage:** `echo "Москва café 😀" | python -m tools.unicode_normalizer normalize`
(`anyascii` dep; invoke via Kitbash `.venv` with `PYTHONPATH= `.)

### pattern_confidence_scorer
**Status:** Implemented (Tier 2 meta-learning; stdlib only). 4 functions: score_patterns_against_traces (sequence/collision/grain_chain matching → TP/FP/TN/FN → precision/recall/F1/TPR/FPR/specificity/support + reliability + flags + aggregate), score_patterns_against_dream_bucket (JSONL observations), compare_pattern_reliability (traces vs dream_bucket + divergence), decay_confidence_by_age (exp decay by age). **Spec deviation:** implements STANDARD textbook FPR=FP/(FP+TN) & specificity=1−FPR. The SPEC prose is loose; `TEST-pattern_confidence_scorer_examples.json` was regenerated to be internally consistent (FPR+specificity=1, f1=2PR/(P+R)) and now serves as the acceptance fixture — every case's output is asserted equal to its `expected_output`. Errors: ValueError→1, FileNotFoundError/OSError/RuntimeError→2. Exit 0/1/2.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-pattern_confidence_scorer_v1.md` · **Code:** `pattern_confidence_scorer/` (+ `metrics.py`, `pattern_matching.py`, `scorer_schema.py`, 8 files) · **Usage:** `python -m tools.pattern_confidence_scorer score-traces --patterns p.json --traces t.jsonl`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### anomaly_scorer
**Status:** Implemented (Tier 2 introspection triad; stdlib only). 5 functions: detect_false_positive_rate_anomalies (FP-rate spikes/drops vs baseline, ratio>2 or z>3), detect_confidence_degradation (violation-rate climb + increasing trend), detect_emerging_collisions (new/accelerating pairs), detect_violation_trend_shifts (reversal/acceleration), score_anomaly_severity (recency boost). Severity = monotonic magnitude curve (2–3×→0.4, >10×→0.95) + modifiers; recency factor `1+(w-1)e^-age·0.1`. Errors: ValueError→1, OSError/RuntimeError→2. Exit 0/1/2. **Spec note:** SPEC's numeric examples are illustrative (deviation uses `(obs-base)/base`; severity points/bounds are guides); TEST `severity_min/max` bounds respected. **Test:** `TEST-anomaly_scorer_examples.json`.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-anomaly_scorer_v1.md` · **Code:** `anomaly_scorer/` (+ `baselines.py`, `severity_calculator.py`, `cause_suggester.py`, `anomaly_schema.py`, 8 files) · **Usage:** `python -m tools.anomaly_scorer detect-fp-spikes --grain-stats g.json --historical-baseline b.json`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### pattern_explainer
**Status:** Implemented (Sleep Tier 2 introspection; stdlib only). Explains collision clusters, anomalies (from anomaly_scorer), pattern reliability (from pattern_confidence_scorer), and multi-pattern reports. 5 functions: explain_collision_cluster, explain_anomaly, explain_pattern_reliability, explain_multiple_patterns, generate_sleep_report. Template-based plain-language (no LLM/NLP). Errors: ValueError→1, RuntimeError→2. Exit 0/1/2. **Spec deviation:** f1 "high" reliability = F1>=0.70 (SPEC prose shows 0.75; TEST `explain_multiple_patterns` asserts high>=6, only satisfiable at 0.70). **Test:** `TEST-pattern_explainer_examples.json`.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-pattern_explainer_v1.md` · **Code:** `pattern_explainer/` (+ `templates.py`, `formatters.py`, `confidence_language.py`, `explainer_schema.py`, 9 files) · **Usage:** `python -m tools.pattern_explainer explain-pattern --pattern p.json --confidence-scores s.json`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### cosine_similarity
**Status:** Implemented (vector math; stdlib only). 4 functions: compute_similarity (lists or TF-IDF dicts, sparse-safe, normalize=True default), compute_similarity_matrix (N×N, off-diagonal stats + highest/lowest pairs), compute_vector_neighbors (top-k KNN + outlier flag), compare_vector_sets (cross-similarity). Deterministic, no ML. Errors: ValueError→1, OSError→2. Exit 0/1/2. **Spec deviation:** corrected TEST bounds that were mathematically impossible (true normalized cosine differs from SPEC prose examples — e.g. the "0.856" single-pair case is actually 0.955). **Test:** `TEST-cosine_similarity_examples.json`.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-cosine_similarity_v1.md` · **Code:** `cosine_similarity/` (+ `vector_utils.py`, `matrix_stats.py`, `similarity_schema.py`, 8 files) · **Usage:** `python -m tools.cosine_similarity compute-pair --vector-a "[1,0,0]" --vector-b "[0,1,0]"`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### trie
**Status:** Implemented (prefix-tree; stdlib only). 8 functions: build_trie (nested-dict, case-sensitive flag), search_trie (exact match + path traversal), prefix_search, suggest_completions (autocomplete), negation_search (exclude-by-prefix), get_trie_stats, serialize_trie / deserialize_trie (JSON round-trip). Errors: ValueError→1, RuntimeError→2. Exit 0/1/2. **Spec deviation:** TEST `node_count_max` corrected 50→70 (the 6-word canonical vocab spans 70 characters → 61 nodes; SPEC's "34" example was illustrative). **Test:** `TEST-trie_examples.json`.
**Intended output:** JSON-serializable dicts (library + CLI).
**Spec:** `SPEC-trie_v1.md` · **Code:** `trie/` (+ `trie_node.py`, `negation.py`, `serialization.py`, `trie_schema.py`, 9 files) · **Usage:** `python -m tools.trie build --vocabulary vocab.jsonl --output trie.json`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### episode_annotation_tool
**Status:** Implemented (CWL episode boundary marking; stdlib only). Marks exploratory (`expl`) vs. action (`act`) episode boundaries; writes SPEC-shaped records (`episode_id, phase, summary, timestamp, session_id, query_id, agent_context`) to JSONL. `episode_id` = `{phase}_{YYYYmmdd_HHMMSS}_{uuid8}`. Invalid phase / empty summary → `{"status":"error",...}` (never raises). Write-only, non-blocking. **Isolation note:** SPEC postcondition is `DreamBucketWriter.append("episodes", record)`; importing `dream_bucket.py` would violate the tools/ Isolation Contract, so this writes JSONL to a configurable `log_path` (default `dream_bucket/live/episodes.jsonl`) via stdlib — format-compatible with the real `episodes` log type, with a `writer` arg for drop-in Dream Bucket wiring. **Test:** `TEST-episode_annotation_tool_examples.json` (generated; no upstream TEST existed).
**Intended output:** JSON-serializable dict (library + CLI).
**Spec:** `SPEC-episode_annotation_tool_v1.md` · **Code:** `episode_annotation_tool/` (+ `core.py`, `cli.py`, `__init__.py`, `__main__.py`, `README.md`, 6 files) · **Usage:** `python -m tools.episode_annotation_tool annotate --phase expl --summary "read thermodynamics_general cartridge"`
(Pure stdlib; same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.)

### math_evaluation
**Status:** Implemented (arithmetic; stdlib only). Safe `ast`-based evaluation (no `eval`/`exec`, no builtins except `math`): `safe_evaluate(expression, precision=10)`. Supports `+ - * / // % **` (and `^` as exponentiation), `sqrt/abs/sin/cos/tan/log/ln/log10/exp/ceil/floor/min/max/...`, constants `pi e tau inf nan`. Result int when integral else float; `/` always float. Errors (invalid syntax, undefined variable, math domain, division by zero, overflow) → `{"status":"error",...}`, never raised. **Spec:** `SPEC-math_evaluation_v1.md` · **Test:** `TEST-math_evaluation_examples.json` · **Code:** `math_evaluation/` · **Usage:** `python -m tools.math_evaluation evaluate "2 + 2 * 3"`. (Pure stdlib; `PYTHONPATH= ` prefix.)

### unit_conversion
**Status:** Implemented (units; stdlib only). `convert_units(value, from_unit, to_unit, precision=2)` across 6 categories (temperature, distance, weight, volume, time, area) with full-name + alias support (C/F/K, km/m, kg/lb, …). Temperature absolute (C↔F↔K); others factor-to-base. Unknown unit returns `did you mean?` hint; incompatible category errors; all returned as dicts, never raised. **Spec:** `SPEC-unit_conversion_v1.md` · **Test:** `TEST-unit_conversion_examples.json` · **Code:** `unit_conversion/` · **Usage:** `python -m tools.unit_conversion convert 100 celsius fahrenheit`. (Pure stdlib; `PYTHONPATH= ` prefix.)

### templating
**Status:** Implemented (string interpolation; stdlib only). `template_render(template, variables, mode="strict")` wraps `string.Template`: strict (default) errors on missing variable, lenient leaves `$placeholder` intact; `$$` → literal `$`; values serialized via `str()`/JSON. `extract_variables(template)` for logging. Errors → `{"status":"error",...}`, never raised. **Spec:** `SPEC-templating_v1.md` · **Test:** `TEST-templating_examples.json` · **Code:** `templating/` · **Usage:** `python -m tools.templating render "Hello $name" '{"name":"Alice"}'`. (Pure stdlib; `PYTHONPATH= ` prefix.)

### diff_patch
**Status:** Implemented (unified diff generate/apply; stdlib only). `diff_generate(text_a, text_b, context_lines=3)` uses `difflib.unified_diff`; `diff_apply(text, patch)` parses hunks and applies with 1-line fuzz tolerance. Binary (null-byte) input errors; mismatched context → `{"status":"error","reason":"Patch does not apply cleanly:..."}`. Errors returned as dicts, never raised. **Spec:** `SPEC-diff_patch_v1.md` · **Test:** `TEST-diff_patch_examples.json` · **Code:** `diff_patch/` · **Usage:** `python -m tools.diff_patch generate a.txt b.txt --context 1`. (Pure stdlib; `PYTHONPATH= ` prefix.)

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
