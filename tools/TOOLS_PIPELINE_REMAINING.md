# Tools Pipeline: Remaining & Prioritized

**Status:** Post-spec planning  
**Date:** 2026-07-14  
**Purpose:** Roadmap of remaining tools (post v1 MVP core), including new lightweight library suggestions, organized by priority and sequencing

---

## Already Specced ✅ (11 tools)

These have full SPEC files; all 11 built and shipped:

1. DateTime Utilities v1 ✅ (built & shipped)
2. Neighborhood Projection v1 ✅ (built & shipped)
3. Log Parser v1 ✅ (built & shipped)
4. Sequence Pattern Miner v1 ✅ (built & shipped)
5. Text Search v1 ✅ (built & shipped)
6. Conditional Pattern Detector v1 ✅ (built & shipped; target=grain_present_in_chain, computable types only)
7. Line Filtering v1 ✅ (built & shipped)
8. JSON Query/Filter v1 ✅ (built & shipped; all 46 test cases pass)
9. Filesystem Access v1 ✅ (built & shipped; config-driven Airlock boundaries)
10. Contractions v1 ✅ (built & shipped; `contractions` PyPI dep)
11. CSV Operations v1 ✅ (built & shipped; stdlib csv)

---

## Already Built (Document Extractors + Input Sieves) ✅

These exist in codebase; no spec needed:

**Document Extractors (9):**
- txt_extractor, markdown_extractor, html_extractor, json_extractor, docx_extractor, rtf_extractor, odt_extractor, epub_extractor, pdf_extractor (via pypdf)

**Input Sieves (4):**
- Tokenizer v1 (spaCy-based)
- Negation Detector v1 (window-based)
- Named Entity Recognition v1 (spaCy NER)
- Subject-Verb-Object (SVO) Extractor v1 (spaCy dependency)

**Dispatcher & Normalization:**
- Document Dispatcher (routes 9 formats to correct extractor)
- Stage 2 Normalization v1 (whitespace collapse, dedup lines)

---

## Remaining Tools: Prioritized Pipeline

### **TIER 1: Critical Next (High ROI, Unblock Other Tools)**

#### Data Plumbing Utilities

**1. Contractions v1** ⏳ (QUEUED FOR SPEC THIS WEEK)
- **What:** Expand English contractions ("don't" → "do not")
- **Why:** Improves negation_detector accuracy directly. Preprocessing step before tokenizer.
- **Dependencies:** `contractions` (PyPI, tiny)
- **Effort:** Low spec, trivial build
- **Unblocks:** Better NLP accuracy downstream

**2. CSV Operations v1** ⏳ (QUEUED FOR SPEC THIS WEEK)
- **What:** Parse, filter rows, select columns, sort (stdlib csv)
- **Why:** Foundational data plumbing; pairs with existing tools
- **Dependencies:** stdlib csv
- **Effort:** Low-medium
- **Unblocks:** Data ingestion workflows

**3. Unicode Normalizer v1 (AnyAscii)** ✅ (built & shipped)
- **What:** Smart Unicode→ASCII transliteration (emojis, accents, non-Latin scripts)
- **Why:** Deterministic text normalization; prevents cosmetic mutations in indexing; pairs with Stage 2 Normalization
- **Dependencies:** `anyascii` (PyPI, zero-dependency)
- **Effort:** Low spec, trivial build
- **Unblocks:** Robust text canonicalization for cartridge indexing

**4. Excel/ODS Extractor v1 (python-calamine)** (SPEC MEDIUM PRIORITY)
- **What:** Extract data from .xlsx, .xls, .ods files (Rust-backed, minimal footprint)
- **Why:** Closes gap in document extractors; lightweight alternative to openpyxl
- **Dependencies:** `python-calamine` (PyPI, Rust-backed but tiny)
- **Effort:** Medium spec (new format), build straightforward
- **Unblocks:** Spreadsheet ingestion workflows

**5. Keyword Search v1 (FlashText)** (SPEC MEDIUM PRIORITY)
- **What:** O(N) dictionary-based keyword matching & replacement (Aho-Corasick algorithm)
- **Why:** Fast PII masking, entity redaction, tagging at scale (outperforms regex for large dictionaries)
- **Dependencies:** `flashtext` (PyPI, zero-dependency)
- **Effort:** Medium spec (new algorithm paradigm), build straightforward
- **Unblocks:** PII masking, entity tagging in cartridge workflows

**6. CSV Dialect Detector v1 (CleverCSV)** (SPEC LATER)
- **What:** Robust CSV dialect detection (delimiter, quote char, escape) on malformed data
- **Why:** Handles messy real-world CSV input; more robust than stdlib csv.Sniffer
- **Dependencies:** `clevercsv` (PyPI)
- **Effort:** Medium spec, build straightforward
- **Unblocks:** Resilient CSV parsing

**7. Archive Manager v1** (SPEC AFTER Keyword Search)
- **What:** Extract and create archives (zip, tar, gzip, bzip2, 7z, xz, zstd) with auto-format detection
- **Why:** Unpack ingested archives; bundle results for export; common data format
- **Dependencies:** stdlib (zip, tarfile, gzip, bz2) + `py7zr` (PyPI, 7z support) + `rarfile` (PyPI, RAR read-only v1)
- **Format Support:**
  - Read: zip, tar, tar.gz, tar.bz2, 7z (via py7zr), RAR (read-only via rarfile), gzip, bzip2, xz
  - Write: zip, tar, tar.gz, tar.bz2, gzip, bzip2 (v1.0); RAR creation deferred to v1.1
- **Auto-detect:** Magic byte detection; fail-over to user specification
- **Effort:** Medium-high spec (8 formats, error handling); build straightforward
- **Unblocks:** Archive ingestion workflows, export bundling

---

#### Introspection & Pattern Discovery (Sleep Tier 2)

**7. Pattern Confidence Scorer v1** (SPEC AFTER Conditional Pattern Detector shipping)
- **What:** Measure reliability (precision, recall, F1) of discovered patterns against trace data
- **Why:** Feeds sleep Tier 2; ranks patterns by trustworthiness
- **Dependencies:** stdlib
- **Effort:** Medium spec (metrics design), build straightforward
- **Unblocks:** Tier 2 pattern ranking; meta-learning

**8. Anomaly Scorer v1** (SPEC AFTER Pattern Confidence Scorer)
- **What:** Identify deviations from discovered patterns; flag surprising tool call sequences
- **Why:** Detects reasoning failures; feeds Dream Bucket
- **Dependencies:** stdlib
- **Effort:** Medium spec, build straightforward
- **Unblocks:** Failure detection for sleep pipeline

**9. Pattern Explainer v1** (SPEC AFTER Anomaly Scorer)
- **What:** Generate human-readable summaries of discovered patterns
- **Why:** Sleep Tier 2 report generation; debugging
- **Dependencies:** stdlib (+ Templating tool recommended)
- **Effort:** Medium spec (interpretation logic), build straightforward
- **Unblocks:** Readable pattern reports

---

### **TIER 2: High Priority (Important, Good Composition)**

#### Ingestion & Egress (Category C: External Integration, Gated)

**10. Trie/Prefix Tree v1**
- **What:** Build trie, query with prefix, support negation patterns
- **Dependencies:** stdlib
- **Effort:** Low-medium
- **Use case:** Fast prefix-based lookups (e.g., command completion, autocorrect)

**11. TF-IDF Ranker v1**
- **What:** Calculate TF-IDF scores, rank documents by relevance
- **Dependencies:** stdlib collections
- **Effort:** Medium
- **Use case:** Document relevance ranking without semantic similarity

**12. Boolean Search v1**
- **What:** Parse and evaluate boolean queries (AND/OR/NOT) against corpus
- **Dependencies:** stdlib re
- **Effort:** Medium
- **Use case:** Query expansion, complex text filtering

**13. Inverted Index Builder v1**
- **What:** Build term→doc_id index, serialize, support queries
- **Dependencies:** stdlib
- **Effort:** Medium
- **Use case:** Fast term-based document lookup

**14. Markov Chain v1**
- **What:** Build n-gram state transitions, query transitions, generate sequences
- **Dependencies:** stdlib collections
- **Effort:** Medium
- **Use case:** Sequence generation from procedural edge graphs

**15. Naive Bayes Classifier v1**
- **What:** Learn class priors/word frequencies, classify new text
- **Dependencies:** stdlib math, collections
- **Effort:** Medium-high
- **Use case:** Text classification without neural networks

**16. Frequency Analysis v1**
- **What:** Count terms, compute distributions, calculate entropy
- **Dependencies:** stdlib collections
- **Effort:** Low-medium
- **Use case:** Text statistics, distribution analysis

---

#### Ingestion & Egress (Category C: External Integration, Gated)

**17. RSS Feed Fetcher v1**
- **What:** Fetch RSS/Atom feed, parse entries, write to inbox/external/
- **Dependencies:** stdlib urllib + xml.etree.ElementTree
- **Effort:** Medium
- **Safety:** Writes to inbox/external/ only (Airlock quarantine)
- **Use case:** Feed ingestion for knowledge synthesis

**18. Raw HTTP/HTTPS Ingester v1**
- **What:** Deterministic HTTP GET request, write to inbox/external/
- **Dependencies:** stdlib urllib.request
- **Effort:** Low-medium
- **Safety:** No ambient proxy; config-driven only; Airlock quarantine
- **Use case:** Fetch single resource from web

**19. IMAP Single-Message Fetcher v1**
- **What:** Authenticate via IMAP, download oldest/newest unread email, mark as read
- **Dependencies:** stdlib imaplib, email
- **Effort:** Medium
- **Safety:** Write to inbox/external/ only; credentials from config
- **Use case:** Email ingestion for agent workflows

**20. DNS Resource Record Lookup v1**
- **What:** Query domain for A, AAAA, MX, CNAME, TXT records
- **Dependencies:** stdlib socket
- **Effort:** Low
- **Safety:** Local network only; no ambient DNS proxy
- **Use case:** DNS queries for network-based task automation

**21. Webhook Egress Poster v1**
- **What:** Post local outbox/ data to pre-validated remote webhook
- **Dependencies:** stdlib urllib.request, json
- **Effort:** Low-medium
- **Safety:** Pre-approved destinations only (from config)
- **Use case:** Push results to external systems (discord, slack, custom webhook)

**22. Home Assistant Bridge v1**
- **What:** Direct REST interaction with Home Assistant instance (query states, trigger services)
- **Dependencies:** stdlib urllib.request, json
- **Effort:** Medium
- **Safety:** Local network only; credentials from config
- **Use case:** IoT/home automation integration

---

#### Data Integrity & DAG Analysis

**23. Simple Version Control v1**
- **What:** Store timestamped snapshots, retrieve older versions, log modifications
- **Dependencies:** stdlib (file I/O + JSON)
- **Effort:** Medium
- **Use case:** Audit trail for workspace files; rollback capability

**24. Data Validation v1**
- **What:** Validate data against schemas (JSON schema, regex patterns, type checks)
- **Dependencies:** stdlib (+ fastjsonschema optional for performance)
- **Effort:** Low-medium
- **Use case:** Input validation at boundaries

**25. DAG Dependency Resolver v1**
- **What:** Resolve tasks with variable interdependencies into linear execution sequence
- **Dependencies:** stdlib graphlib.TopologicalSorter (Python 3.9+)
- **Effort:** Medium
- **Use case:** Task scheduling, orchestration logic

---

#### Graph & Time-Series Topology

**26. Edge Weight Mutation v1**
- **What:** Apply violation signals / confidence updates to procedural edge weights
- **Dependencies:** stdlib
- **Effort:** Low
- **Use case:** Dream Bucket → Procedural Edge Graph updates

**27. Time Series / Windowed Operations v1**
- **What:** Aggregate time-series data over sliding/fixed windows
- **Dependencies:** stdlib statistics, collections
- **Effort:** Low-medium
- **Use case:** Dream Bucket statistics, grain activation patterns, topological drift monitoring

---

#### Advanced Text & String Operations

**28. Text Set Operations v1**
- **What:** Mathematical set operations (union, intersection, difference, symmetric difference) on text files/JSON arrays
- **Dependencies:** stdlib set
- **Effort:** Low
- **Use case:** Comparing entity lists, deduping across sources

**29. Content Identifier / Deterministic Hasher v1**
- **What:** Generate content-addressable fingerprints (SHA-256) from text/JSON (with recursive sorting for determinism)
- **Dependencies:** stdlib hashlib, json
- **Effort:** Low
- **Use case:** Deduplication, content verification

**30. Text Canonicalizer & Slugifier v1**
- **What:** Standardize text strings (smart quotes, accents, punctuation, casing) to prevent cosmetic mutations
- **Dependencies:** stdlib unicodedata, re
- **Effort:** Low-medium
- **Use case:** Index stability, entity matching

---

#### Routing & Deterministic Utilities

**31. String Distance / Typo Correction v1 (RapidFuzz)**
- **What:** C++ optimized Levenshtein, Jaro-Winkler, token sorting
- **Why:** Typo detection, "did you mean?" fallback for tool names/params
- **Dependencies:** `rapidfuzz` (PyPI, C++ wrapped)
- **Effort:** Low
- **Use case:** Typo correction for query routing (skip if low priority for v1)

**32. Templating v1**
- **What:** Variable substitution and string interpolation
- **Dependencies:** stdlib string.Template (or lightweight jinja2)
- **Effort:** Low
- **Use case:** Report generation, dynamic text construction

**33. Diff/Patch v1**
- **What:** Generate unified diffs, apply patches
- **Dependencies:** stdlib difflib
- **Effort:** Low
- **Use case:** Text change inspection, code review workflows

**34. Duplicate Detection v1**
- **What:** Find exact and near-duplicate items using sequence matching
- **Dependencies:** stdlib difflib
- **Effort:** Low-medium
- **Use case:** Deduplication, data quality checks

**35. Hypergraph Traversal v1**
- **What:** Traverse JSON hypergraph, find paths, query neighborhoods
- **Dependencies:** stdlib
- **Effort:** Medium
- **Use case:** Graph queries beyond procedural edges

---

### **TIER 3: Lower Priority (Nice-to-Have, Deferred)**

**36. Success Pattern Miner v1** (Positive-Signal Discovery)
- **What:** Identify recurring tool sequences in successful traces (complements Anomaly Scorer)
- **Dependencies:** stdlib collections, itertools
- **Effort:** Medium
- **Use case:** Learn from successes (not just failures); meta-learning

**37. Positive Signal Scorer v1** (Serendipity Detection)
- **What:** Flag unexpected successes where pipeline succeeded despite low-confidence elements
- **Dependencies:** stdlib
- **Effort:** Medium
- **Use case:** Identify lucky/clever reasoning paths

**38. Causal Credit Attribution v1** (Ablation Analysis)
- **What:** Run ablation analysis on successful traces; measure which tool calls were causally necessary vs. redundant
- **Dependencies:** stdlib
- **Effort:** High (complex analysis logic)
- **Use case:** Optimize tool chains; identify wasteful steps

**39. Topological Statistics v1**
- **What:** Monitor procedural edge graph health (degree distribution, density, avg path length, component count)
- **Dependencies:** stdlib
- **Effort:** Medium
- **Use case:** Detect degenerate graph shapes; monitor topology drift

**40. Fact Lookup / Retrieval Service** (Queryable Memory Interface)
- **What:** Internal prompt against cartridge system; expose memory as queryable interface
- **Dependencies:** Integration with cartridge system + orchestrator
- **Effort:** High (architectural)
- **Use case:** Reasoning layer queries its own memory during inference
- **Status:** Needs more deconstruction before spec

---

### **TIER 4: Post-2.0 / Future (Image & Audio)**

**41. Local Speech-to-Text (STT) v1**
- **What:** Transcribe .wav, .mp3, .ogg to text (quantized local engine)
- **Dependencies:** whisper.cpp Python bindings or onnxruntime
- **Effort:** Medium (consent-gated asset download)
- **Safety:** Consent-gated model download
- **Use case:** Voice input for agent workflows

**42. Local Text-to-Speech (TTS) v1**
- **What:** Synthesize speech .wav from text (small-footprint local model)
- **Dependencies:** Piper TTS or system-native wrappers
- **Effort:** Medium (consent-gated asset download)
- **Safety:** Consent-gated model download
- **Use case:** Voice output for agent responses

**43. Image Metadata & Exif Extractor v1**
- **What:** Read image dimensions, format, color space, EXIF tags
- **Dependencies:** Pillow
- **Effort:** Low
- **Use case:** Image analysis, metadata extraction

**44. Image Transcoder & Resizer v1**
- **What:** Downscale, adjust quality, convert formats (PNG→JPEG)
- **Dependencies:** Pillow
- **Effort:** Low-medium
- **Use case:** Image normalization, storage optimization

**45. Local Image Edge Feature Detector v1**
- **What:** Extract structural visual features for similarity checking
- **Dependencies:** Pillow or light math processing
- **Effort:** Medium
- **Use case:** Visual similarity, basic feature analysis

**46. Edge Vision Classifier (Tiny) v1**
- **What:** Local image classification via quantized tiny neural net
- **Dependencies:** onnxruntime
- **Effort:** Medium (consent-gated asset download)
- **Safety:** Consent-gated model download
- **Use case:** Local image classification without cloud

---

## Sequencing Recommendation (Updated)

### **This Week (Finishing + Queued)**

> **All three shipped (2026-07-14):** Filesystem Access v1, Contractions v1, CSV Operations v1 — built, verified, and committed. Unicode Normalizer v1 (AnyAscii) also built & shipped (was in Next Week).

### **Next Week (Post-Filesystem)**

4. ~~Unicode Normalizer v1 (AnyAscii)~~ ✅ **built & shipped** (text pipeline completion)
5. **Pattern Confidence Scorer v1** — Continues sleep Tier 2 chain
6. **Anomaly Scorer v1** — Completes introspection triad

### **Following 2 Weeks (Conditional)**

7. **Excel/ODS Extractor v1** — Closes document gap
8. **Keyword Search v1 (FlashText)** — Text processing scalability
9. **Archive Manager v1** — Multi-format archive extraction + bundling

### **Post-MVP Roadmap (Backlog)**

- Introspection tools (Tier 3): Success Pattern Miner, Positive Signal Scorer, Causal Credit Attribution
- Historical AI techniques (Tier 2): Trie, TF-IDF, Boolean Search, Inverted Index, Markov, Naive Bayes
- Ingestion/Egress (Tier 2): RSS, HTTP, IMAP, DNS, Webhook, Home Assistant
- Audio/Vision (Tier 4): STT, TTS, Image utilities

---

## Summary: Tool Counts

- **Specced & Built (11):** all 11 complete & shipped (DateTime, Neighborhood Projection, Log Parser, Sequence Pattern Miner, Text Search, Conditional Pattern Detector, Line Filtering, JSON Query/Filter, Filesystem Access, Contractions, CSV Operations)
- **Built (13):** Extractors + input sieves + dispatcher + normalization
- **Remaining to Spec (35):**
  - Tier 1 (Post-Queue, 4): Excel Extractor, Keyword Search, CSV Dialect Detector, Archive Manager
  - Tier 2 (High Priority, 22): Historical AI + Ingestion/Egress + Data Integrity + Graph/Time-Series + Text Ops + Routing
  - Tier 3 (Lower Priority, 4): Success Pattern Miner, Positive Signal Scorer, Causal Credit Attribution, Topological Statistics
  - Tier 4 (Post-2.0, 4): STT, TTS, Image metadata, Image transcoder, Image features, Image classifier

**Total with new suggestions: 58 tools** (11 specced & built, 13 built baseline, 34 remaining)

---

**Last updated:** 2026-07-14 (updated — 11/11 specced shipped; Unicode Normalizer also shipped)  
**For:** Isaac & team (roadmap + prioritization)  
**Status:** 12 tools shipped this cycle (11 specced + Unicode Normalizer); Filesystem Access, Contractions, CSV Operations, Unicode Normalizer all verified & committed. Remaining pipeline: 34 tools across Tiers 1–4.
