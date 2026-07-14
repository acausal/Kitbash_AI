# Atomic Tools Brainstorm — 2026-07-13 (Updated)

**Context:** Two-week operational data window. Building Lego bricks first; no orchestration logic yet. Standard agent/chat tool equivalents + custom Kitbash utilities.

---

## Pending Spec ✍️
*Ready to write; no major deconstruction needed*

### Data Plumbing (8 tools)

1. **DateTime Utilities v1**
   - Scope: Parse, format, duration calculation, timezone handling, current time queries  
   - Dependencies: stdlib `datetime` + `pytz`  
   - Output: JSON (ISO strings, seconds, timezone names)  
   - Non-goals: Cron syntax, natural language ("next Tuesday"), calendar ops, i18n  

2. **Text Search v1**
   - Scope: Pattern matching via stdlib `re`, CLI with flags (case-insensitive, multiline, etc.), line numbers + context  
   - Dependencies: stdlib `re` (maybe `regex` for fancier patterns later)  
   - Output: Matches with line numbers, configurable context lines  
   - Non-goals: Performance optimization (ripgrep is separate tool if needed), full grep feature parity  

3. **Filesystem Access v1**
   - Scope: Read, write, list, delete with path validation; configurable base paths  
   - Allowed by default: workspace/, scratch/, inbox/, outbox/, cartridges/ (read-only)  
   - Denied by default: Writes to cartridges/, symlink following, recursive unlisted dirs  
   - Dependencies: stdlib `os`, `pathlib`  
   - Output: JSON (file metadata, operation results, structured errors)  
   - Config: YAML/JSON file specifying base paths; users can override permissions  
   - Non-goals: Security sandboxing (assume trusted user), permission management, file watching  

4. **Math Evaluation v1**
   - Scope: Evaluate arithmetic expressions, return result  
   - Input: Expression string (e.g., "2 + 2 * 3")  
   - Output: Result (number) or error  
   - Dependencies: stdlib `math` (or safe eval wrapper)  
   - Non-goals: Symbolic math, complex numbers, calculus  

5. **Unit Conversion v1**
   - Scope: Convert between units (temperature, distance, weight, common units)  
   - Input: value + from_unit + to_unit  
   - Output: converted value  
   - Dependencies: stdlib + static conversion tables  
   - Non-goals: Exotic units, real-time currency (use static tables), currency conversion (v2)  

6. **JSON Query/Filter v1**
   - Scope: Extract fields, filter, select from JSON  
   - Input: JSON + query (jq-like path/filter)  
   - Output: Filtered JSON  
   - Dependencies: stdlib `json`  
   - Non-goals: Complex transformations, aggregations, joins (v2)  

7. **CSV Operations v1**
   - Scope: Parse, filter rows, select columns, sort  
   - Input: CSV + operation  
   - Output: CSV  
   - Dependencies: stdlib `csv`  
   - Non-goals: Joins, aggregations, complex transforms (v2)  

8. **Line Filtering v1**
   - Scope: Sort, dedup, unique on text lines  
   - Input: Text lines + operation  
   - Output: Text lines  
   - Dependencies: stdlib  
   - Non-goals: Complex patterns (use text search), regex filtering (text search), joins  

---

### Historical AI Techniques (7 tools)

9. **Trie/Prefix Tree v1**
   - Scope: Build trie from word list, query with prefix, support negation patterns  
   - Input: Word list (build) + prefix query (search)  
   - Output: Matching entries or rejection  
   - Negation: Support exclude-prefix patterns ("starts with X but not Y")  
   - Dependencies: stdlib (custom dict-of-dicts implementation)  
   - Non-goals: Fuzzy matching, edit distance, balancing  

10. **TF-IDF Ranker v1**
    - Scope: Calculate TF-IDF scores, rank documents by relevance  
    - Input: Document corpus + query terms  
    - Output: Ranked documents (score, doc_id, snippet)  
    - Dependencies: stdlib `collections`  
    - Non-goals: LSA, semantic similarity, neural ranking  

11. **Boolean Search v1**
    - Scope: Parse and evaluate boolean queries (AND/OR/NOT) against corpus  
    - Input: Text corpus + boolean query  
    - Output: Matching lines/documents  
    - Dependencies: stdlib `re`  
    - Non-goals: Complex query optimization, nested parens (v2)  

12. **Inverted Index Builder v1**
    - Scope: Build term→doc_id index from corpus, serialize, support queries  
    - Input: Document corpus  
    - Output: Inverted index (JSON), query results  
    - Dependencies: stdlib  
    - Non-goals: Stemming (v2), fuzzy matching, real-time updates  

13. **Markov Chain v1**
    - Scope: Build n-gram state transitions from text, query transitions, generate sequences  
    - Input: Text corpus  
    - Output: State transitions with probabilities (JSON), or generated text  
    - Dependencies: stdlib `collections`  
    - Non-goals: Smoothing, variable order (v2), neural language models  

14. **Naive Bayes Classifier v1**
    - Scope: Learn class priors/word frequencies from training data, classify new text  
    - Input: Training data (text + label) + test text  
    - Output: Classification + confidence score  
    - Dependencies: stdlib `math`, `collections`  
    - Non-goals: Multi-class with many features (v2), feature engineering  

15. **Frequency Analysis v1**
    - Scope: Count terms, compute distributions and statistics  
    - Input: Text corpus  
    - Output: Term frequencies, statistics (common, rare, entropy, distributions)  
    - Dependencies: stdlib `collections`  
    - Non-goals: Visualization, advanced statistics (v2)  

---

### Ingestion & Transformation (5 tools)

16. **RSS Feed Fetcher v1**
    - Scope: Fetch RSS/Atom feed, parse entries, write timestamped JSON to workspace  
    - Input: Feed URL  
    - Output: Creates timestamped JSON file with parsed entries  
    - Dependencies: stdlib `urllib` + `xml.etree.ElementTree` (or `feedparser`)  
    - Non-goals: Scheduling, filtering, deduplication, storage management  

17. **Templating v1**
    - Scope: Variable substitution and string interpolation in text  
    - Input: Template string + variables (JSON/dict)  
    - Output: Rendered text  
    - Dependencies: stdlib `string.Template` (or lightweight jinja2)  
    - Non-goals: Logic in templates (v2), complex filters, inheritance  

18. **Diff/Patch v1**
    - Scope: Generate unified diffs between two texts, apply patches  
    - Input: Text A + Text B (for diff), or Text + Patch (for apply)  
    - Output: Unified diff, or patched text  
    - Dependencies: stdlib `difflib`  
    - Non-goals: Binary diffs, complex patch format support (v2)  

19. **Duplicate Detection v1**
    - Scope: Find exact and near-duplicate items in corpus  
    - Input: Text corpus or list of items + similarity threshold  
    - Output: Grouped duplicates with match scores  
    - Dependencies: stdlib (maybe `difflib` for similarity)  
    - Non-goals: Semantic similarity (different tool), image dedup, performance on massive corpora (v2)  

20. **Hypergraph Traversal v1**
    - Scope: Traverse JSON hypergraph, find paths, query neighborhoods  
    - Input: JSON hypergraph (nodes + hyperedges) + start node + traversal type (DFS/BFS/neighbors)  
    - Output: Paths, neighbors, or full traversal result (JSON)  
    - Dependencies: stdlib  
    - Non-goals: Optimization, cycle detection (v2), SQLite integration, weighted edges  

---

### Data Integrity (2 tools)

21. **Simple Version Control v1**
    - Scope: Store timestamped snapshots of files, retrieve versions, log changes  
    - Input: File path + operation (save/restore/log)  
    - Output: Version history (JSON) or restored file  
    - Dependencies: stdlib (file I/O + JSON)  
    - Non-goals: Merging, diffs, branching, full Git feature parity  

22. **Data Validation v1**
    - Scope: Validate data against schemas (JSON schema, regex patterns, type checks)  
    - Input: Data + validation rules (schema)  
    - Output: Valid/invalid + error details  
    - Dependencies: stdlib (maybe `jsonschema` for JSON schema support)  
    - Non-goals: Custom validators (v2), complex conditional rules  

---

### Graph & Time-Series Analysis (3 tools) — NEW

23. **Neighborhood Projection v1**
    - Scope: Query procedural edge graph; given seed node(s), return local neighborhood weighted by edge strength  
    - Input: Seed node ID(s) + procedural edge graph JSON + optional strength threshold + optional depth limit  
    - Output: Neighborhood JSON (nodes + weighted edges + aggregated metadata)  
    - Use case: Query-time context expansion; "find facts related to this concept via learned co-occurrence topology"  
    - Dependencies: stdlib  
    - Note: Already exists embedded in sleep pipeline; exposing as standalone tool for flexibility  
    - Non-goals: Cycle detection, path finding, optimization  

24. **Edge Weight Mutation v1**
    - Scope: Apply violation signals / confidence updates to procedural edge weights  
    - Input: Edge graph JSON + mutations (edge_id → delta, or batch updates)  
    - Output: Updated edge graph JSON  
    - Use case: Integrate dream bucket signals into topology post-sleep  
    - Dependencies: stdlib  
    - Note: Lives in sleep pipeline; exposing for debugging and manual annotation flows  
    - Non-goals: Merging conflicting updates, time-series history (use Version Control)  

25. **Time Series / Windowed Operations v1**
    - Scope: Aggregate time-series data over sliding or fixed windows  
    - Input: Array of (timestamp, value) tuples + window size + operation (sum/mean/median/entropy/count)  
    - Output: Windowed results with timestamps  
    - Use cases: Dream bucket statistics, grain activation patterns, topological drift monitoring  
    - Dependencies: stdlib `statistics`, `collections`  
    - Non-goals: Forecasting, smoothing, real-time streaming  

---

### Introspection & Pattern Discovery (6 tools) — NEW

26. **Log Parser v1**
    - Scope: Ingest execution traces (query, grains fired, tool calls, results) into structured format  
    - Input: Raw execution log (JSON or text stream)  
    - Output: Structured trace objects (JSON): query, timestamp, grains_activated, tool_calls_sequence, outcome  
    - Use case: Prepare traces for pattern mining; sleep Tier 2 meta-learning  
    - Dependencies: stdlib `json`, `datetime`  
    - Non-goals: Log rotation, compression, real-time streaming  

27. **Sequence Pattern Miner v1**
    - Scope: Find recurring tool call sequences and n-gram patterns in execution traces  
    - Input: Structured traces (from Log Parser) + n-gram size  
    - Output: Frequent sequences with occurrence counts + probabilities (JSON)  
    - Use case: Discover "when query type X, tool sequence Y→Z→W always follows"  
    - Dependencies: stdlib `collections`, `itertools`  
    - Non-goals: Variable-order Markov (v2), performance on massive trace corpora  

28. **Conditional Pattern Detector v1**
    - Scope: Identify association rules and decision patterns ("when condition X, outcome Y follows with confidence Z")  
    - Input: Structured traces + optional seed conditions (e.g., "grain_type=Z", "confidence < 0.6")  
    - Output: Conditional patterns (JSON): condition, consequent, confidence, support, lift  
    - Use case: Precondition inference for tools; harness optimization  
    - Dependencies: stdlib `collections`  
    - Non-goals: Complex conditional logic (v2), optimization of rule discovery  

29. **Pattern Confidence Scorer v1**
    - Scope: Measure reliability of discovered patterns against trace data  
    - Input: Patterns (sequences or conditionals) + traces  
    - Output: Confidence scores (precision, recall, F1) for each pattern  
    - Use case: Rank patterns by reliability; identify stable vs. noisy patterns  
    - Dependencies: stdlib  
    - Non-goals: Statistical significance tests (v2)  

30. **Anomaly Scorer v1**
    - Scope: Identify unexpected tool calls or deviations from discovered patterns  
    - Input: Patterns + current execution trace  
    - Output: Anomaly score (0–1) + explanation (which pattern was violated?)  
    - Use case: Detect reasoning failures; flag surprising behavior for Dream Bucket  
    - Dependencies: stdlib  
    - Non-goals: Outlier detection via statistical methods (v2)  

31. **Pattern Explainer v1**
    - Scope: Generate human-readable summaries of discovered patterns  
    - Input: Patterns + confidence scores + optional trace snippets  
    - Output: Natural language descriptions ("When query mentions [X], tool [Y] is called 85% of the time")  
    - Use case: Sleep Tier 2 report generation; debugging  
    - Dependencies: stdlib (Templating tool recommended)  
    - Non-goals: Causal inference, multi-step explanations (v2)

---

## Brainstorming 🗺️
*Discussed, needs more deconstruction before spec*

### 1. Fact Lookup / Retrieval (as queryable service)
**Current state:** Dream Bucket + grains feed into query context (sidecar). Read-only.  
**Vision:** Internal prompt against cartridge system; expose memory as queryable interface during reasoning.  
**Intent:** Not a separate debug interface — the reasoning layer asks the cartridge system a question and gets back ranked results.  
**Open questions:**
- Query semantics: Natural language vs. structured (grain_id, time range)?
- Scope: Dream Bucket violations + grain confidences only? Or procedural edges, cartridge states, MTR rankings?
- Output shape: Ranked facts + confidence + context snippets?
- Integration: Does this live in query orchestrator, or as a separate Tool Registry entry?

**Decision:** Pin for further deconstruction. Don't spec yet.

### 2. Topological Statistics v1
**Scope:** Monitor procedural edge graph health: degree distribution, density, average path length, component count  
**Use case:** Detect if topology is drifting toward degenerate shapes (all edges → star, all nodes isolated)  
**Input:** Edge graph JSON  
**Output:** Statistics (JSON): degree histogram, density, avg path length, largest component size, etc.  
**Decision:** Brainstorm; maybe useful post-1.0 for monitoring grain system health  

### 3. Process Control (Deferred)
**Scope:** Run subprocess, capture output, invoke scripts from Tool Registry  
**Status:** Vertical concern; defer for later discussion  

---

## Deferred 🚫
*Flagged but too early to discuss*

### 1. Web Search / Internet Access
**Reason:** Local-first architecture; web access is out of scope  
**Status:** Not applicable

### 2. Cron / Scheduling
**Reason:** Depends on Fact Lookup + query scheduler integration  
**Status:** Post-1.0

### 3. Natural Language Time Parsing ("next Tuesday", "in 2 weeks")
**Reason:** DateTime v1 uses stdlib; fuzzy parsing deferred to v2  
**Status:** Post-DateTime v1

### 4. Environment / Config Querying
**Reason:** Needs architectural decision on single vs. per-cartridge config scope  
**Status:** Defer; revisit with orchestrator config strategy  

---

## Summary

**Pending Spec: 31 tools**
- **Data plumbing (8):** DateTime, Text Search, Filesystem, Math, Unit Conversion, JSON Query, CSV Operations, Line Filtering
- **Historical AI techniques (7):** Trie, TF-IDF, Boolean Search, Inverted Index, Markov Chain, Naive Bayes, Frequency Analysis
- **Ingestion & transformation (5):** RSS Fetcher, Templating, Diff/Patch, Duplicate Detection, Hypergraph Traversal
- **Data integrity (2):** Simple Version Control, Data Validation
- **Graph & time-series (3):** Neighborhood Projection, Edge Weight Mutation, Time Series / Windowed Operations
- **Introspection & pattern discovery (6):** Log Parser, Sequence Pattern Miner, Conditional Pattern Detector, Pattern Confidence Scorer, Anomaly Scorer, Pattern Explainer

**Brainstorming:** Topological Statistics, Fact Lookup/Retrieval (as queryable service), Process Control

**Key principles:**
- Graph learning via procedural edge topology + annotation layer (violation signals, grain confidences) = embedded inductive learning without separate semantic similarity layer
- Neighborhood Projection enables query-time context expansion using learned topology
- Sleep Tier 2 orchestration: Pattern Discovery Service composes tools to enable meta-learning (discover reliable tool call patterns, validate hypotheses, identify reasoning failures)

---

## Notes
- Preserve token space; add items here instead of re-hashing in chat
- When ready to spec an item, move from Brainstorming → Pending Spec
- Scope-locks written before code lands (per discipline)
- Each tool targets stdlib or lightweight PyPI (no heavy deps)
- Neighborhood Projection & Edge Weight Mutation already embedded in sleep pipeline; exposing as standalone tools for Tool Registry flexibility

**Last updated:** 2026-07-13 (evening brainstorm session)
