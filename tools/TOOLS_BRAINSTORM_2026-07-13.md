# Atomic Tools Brainstorm — 2026-07-13

**Context:** Two-week operational data window. Building Lego bricks first; no orchestration logic yet. Standard agent/chat tool equivalents + custom Kitbash utilities.

---

## Pending Spec ✍️
*Ready to write; no major deconstruction needed*

### 1. DateTime Utilities v1
**Scope:** Parse, format, duration calculation, timezone handling, current time queries  
**Dependencies:** stdlib `datetime` + `pytz`  
**Output:** JSON (ISO strings, seconds, timezone names)  
**Non-goals:** Cron syntax, natural language ("next Tuesday"), calendar ops, i18n  
**Status:** Ready for spec write

### 2. Text Search v1
**Scope:** Pattern matching via stdlib `re`, CLI with flags (case-insensitive, multiline, etc.), line numbers + context  
**Dependencies:** stdlib `re` (maybe `regex` for fancier patterns later)  
**Output:** Matches with line numbers, configurable context lines  
**Non-goals:** Performance optimization (ripgrep is separate tool if needed), full grep feature parity  
**Status:** Ready for spec write

### 3. Filesystem Access v1
**Scope:** Read, write, list, delete with path validation; configurable base paths  
**Allowed by default:** workspace/, scratch/, inbox/, outbox/, cartridges/ (read-only)  
**Denied by default:** Writes to cartridges/, symlink following, recursive unlisted dirs  
**Dependencies:** stdlib `os`, `pathlib`  
**Output:** JSON (file metadata, operation results, structured errors)  
**Config:** YAML/JSON file specifying base paths; users can override permissions  
**Non-goals:** Security sandboxing (assume trusted user), permission management, file watching  
**Status:** Ready for spec write

### 4. Math Evaluation v1
**Scope:** Evaluate arithmetic expressions, return result
**Input:** Expression string (e.g., "2 + 2 * 3")
**Output:** Result (number) or error
**Dependencies:** stdlib `math` (or safe eval wrapper)
**Non-goals:** Symbolic math, complex numbers, calculus  
**Status:** Ready for spec write

### 5. Unit Conversion v1
**Scope:** Convert between units (temperature, distance, weight, common units)
**Input:** value + from_unit + to_unit
**Output:** converted value
**Dependencies:** stdlib + static conversion tables
**Non-goals:** Exotic units, real-time currency (use static tables), currency conversion (v2)
**Status:** Ready for spec write

### 6. JSON Query/Filter v1
**Scope:** Extract fields, filter, select from JSON
**Input:** JSON + query (jq-like path/filter)
**Output:** Filtered JSON
**Dependencies:** stdlib `json`
**Non-goals:** Complex transformations, aggregations, joins (v2)
**Status:** Ready for spec write

### 7. CSV Operations v1
**Scope:** Parse, filter rows, select columns, sort
**Input:** CSV + operation
**Output:** CSV
**Dependencies:** stdlib `csv`
**Non-goals:** Joins, aggregations, complex transforms (v2)
**Status:** Ready for spec write

### 8. Line Filtering v1
**Scope:** Sort, dedup, unique on text lines
**Input:** Text lines + operation
**Output:** Text lines
**Dependencies:** stdlib
**Non-goals:** Complex patterns (use text search), regex filtering (text search), joins
**Status:** Ready for spec write

### 9. Trie/Prefix Tree v1
**Scope:** Build trie from word list, query with prefix, support negation patterns
**Input:** Word list (build) + prefix query (search)
**Output:** Matching entries or rejection
**Negation:** Support exclude-prefix patterns ("starts with X but not Y")
**Dependencies:** stdlib (custom dict-of-dicts implementation)
**Non-goals:** Fuzzy matching, edit distance, balancing
**Status:** Ready for spec write

### 10. TF-IDF Ranker v1
**Scope:** Calculate TF-IDF scores, rank documents by relevance
**Input:** Document corpus + query terms
**Output:** Ranked documents (score, doc_id, snippet)
**Dependencies:** stdlib `collections`
**Non-goals:** LSA, semantic similarity, neural ranking
**Status:** Ready for spec write

### 11. Boolean Search v1
**Scope:** Parse and evaluate boolean queries (AND/OR/NOT) against corpus
**Input:** Text corpus + boolean query
**Output:** Matching lines/documents
**Dependencies:** stdlib `re`
**Non-goals:** Complex query optimization, nested parens (v2)
**Status:** Ready for spec write

### 12. Inverted Index Builder v1
**Scope:** Build term→doc_id index from corpus, serialize, support queries
**Input:** Document corpus
**Output:** Inverted index (JSON), query results
**Dependencies:** stdlib
**Non-goals:** Stemming (v2), fuzzy matching, real-time updates
**Status:** Ready for spec write

### 13. Markov Chain v1
**Scope:** Build n-gram state transitions from text, query transitions, generate sequences
**Input:** Text corpus
**Output:** State transitions with probabilities (JSON), or generated text
**Dependencies:** stdlib `collections`
**Non-goals:** Smoothing, variable order (v2), neural language models
**Status:** Ready for spec write

### 14. Naive Bayes Classifier v1
**Scope:** Learn class priors/word frequencies from training data, classify new text
**Input:** Training data (text + label) + test text
**Output:** Classification + confidence score
**Dependencies:** stdlib `math`, `collections`
**Non-goals:** Multi-class with many features (v2), feature engineering
**Status:** Ready for spec write

### 15. Frequency Analysis v1
**Scope:** Count terms, compute distributions and statistics
**Input:** Text corpus
**Output:** Term frequencies, statistics (common, rare, entropy, distributions)
**Dependencies:** stdlib `collections`
**Non-goals:** Visualization, advanced statistics (v2)
**Status:** Ready for spec write

### 16. RSS Feed Fetcher v1
**Scope:** Fetch RSS/Atom feed, parse entries, write timestamped JSON to workspace
**Input:** Feed URL
**Output:** Creates timestamped JSON file with parsed entries
**Dependencies:** stdlib `urllib` + `xml.etree.ElementTree` (or `feedparser`)
**Non-goals:** Scheduling, filtering, deduplication, storage management
**Status:** Ready for spec write

### 17. Templating v1
**Scope:** Variable substitution and string interpolation in text
**Input:** Template string + variables (JSON/dict)
**Output:** Rendered text
**Dependencies:** stdlib `string.Template` (or lightweight jinja2)
**Non-goals:** Logic in templates (v2), complex filters, inheritance
**Status:** Ready for spec write

### 18. Simple Version Control v1
**Scope:** Store timestamped snapshots of files, retrieve versions, log changes
**Input:** File path + operation (save/restore/log)
**Output:** Version history (JSON) or restored file
**Dependencies:** stdlib (file I/O + JSON)
**Non-goals:** Merging, diffs, branching, full Git feature parity
**Status:** Ready for spec write

### 19. Data Validation v1
**Scope:** Validate data against schemas (JSON schema, regex patterns, type checks)
**Input:** Data + validation rules (schema)
**Output:** Valid/invalid + error details
**Dependencies:** stdlib (maybe `jsonschema` for JSON schema support)
**Non-goals:** Custom validators (v2), complex conditional rules
**Status:** Ready for spec write

### 20. Duplicate Detection v1
**Scope:** Find exact and near-duplicate items in corpus
**Input:** Text corpus or list of items + similarity threshold
**Output:** Grouped duplicates with match scores
**Dependencies:** stdlib (maybe `difflib` for similarity)
**Non-goals:** Semantic similarity (different tool), image dedup, performance on massive corpora (v2)
**Status:** Ready for spec write

### 21. Hypergraph Traversal v1
**Scope:** Traverse JSON hypergraph, find paths, query neighborhoods
**Input:** JSON hypergraph (nodes + hyperedges) + start node + traversal type (DFS/BFS/neighbors)
**Output:** Paths, neighbors, or full traversal result (JSON)
**Dependencies:** stdlib
**Non-goals:** Optimization, cycle detection (v2), SQLite integration, weighted edges
**Status:** Ready for spec write

---

## Summary

**Pending Spec: 21 tools**
- **Data plumbing (8):** DateTime, Text Search, Filesystem, Math, Unit Conversion, JSON Query, CSV Operations, Line Filtering
- **Historical AI techniques (7):** Trie, TF-IDF, Boolean Search, Inverted Index, Markov Chain, Naive Bayes, Frequency Analysis
- **Ingestion & transformation (4):** RSS Fetcher, Templating, Duplicate Detection, Hypergraph Traversal
- **Data integrity (2):** Data Validation, Simple Version Control

**Brainstorming: Graph Construction & Projection**
- Build different topologies from same corpus depending on reasoning needs
- Needs more deconstruction before spec

**Deferred to post-1.0:**
- Task scheduling/cron (orchestration, not a tool)
- Code execution (complexity/security concerns)
- Web search (local-first architecture)
- All tools already built (extractors, NER, SVO, negation detector, structured validator, etc.)

---

## Brainstorming 🗺️
*Discussed, needs more deconstruction before spec*

### 1. Fact Lookup / Retrieval (as queryable service)
**Current state:** Dream Bucket + grains feed into query context (sidecar). Read-only.  
**Vision:** Tool to query corpus at any point; expose memory as HUD/queryable interface  
**Open questions:**
- Query semantics: Natural language vs. structured (grain_id, time range)?
- Scope: Dream Bucket violations + grain confidences only? Or procedural edges, cartridge states, MTR rankings?
- Output shape: Ranked facts + confidence + context snippets?
- Use case: "What does the system know about concept X?"

**Decision:** Pin for further deconstruction. Don't spec yet.

### 2. Math/Calculation
**Scope:** Basic arithmetic, transcendentals, maybe symbolic?  
**Flagged in:** POST_MVP_ROADMAP.md (post-1.0)  
**Decision:** Deferred until query classification pipeline clarifies what queries need calculator delegation

### 3. Unit Conversion
**Scope:** Temperature, distance, weight, currency  
**Similar to:** Math tool (routing signal needed first)  
**Decision:** Brainstorm later; low urgency

### 4. Structured Data Querying
**Scope:** Simple SQL-like ops on CSV/JSON (filter, sort, aggregate)  
**Similar to:** Math tool (depends on use case)  
**Decision:** Brainstorm later; depends on what operational data reveals

### 5. Image Metadata / Analysis
**Scope:** Dimensions, EXIF, basic stats  
**Question:** Do you care about images in Kitbash context?  
**Decision:** Ask; may not be relevant

### 6. Code Execution (sandboxed Python eval)
**Scope:** Safe eval of Python expressions  
**Risk:** Complexity, security  
**Decision:** Likely out of scope for near-term; defer to post-1.0

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

---

## Notes
- Preserve token space; add items here instead of re-hashing in chat
- When ready to spec an item, move from Brainstorming → Pending Spec
- Scope-locks written before code lands (per discipline)
- Each tool targets stdlib or lightweight PyPI (no heavy deps)

**Last updated:** 2026-07-13
