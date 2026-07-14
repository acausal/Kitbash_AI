# SPEC: Boolean Search v1

**Module:** `tools/boolean_search/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, re, collections)  
**Priority:** Medium (classical IR; useful for precise matching, log analysis, filtering)

---

## Overview

Retrieve documents using Boolean logic (AND, OR, NOT) over exact token matches. Pure, stateless search: no ranking, no relevance scoring, no probabilistic inference. Return exact set of documents matching query expression.

**Design principle:** Deterministic set operations. Parse Boolean query expression; evaluate against pre-tokenized corpus; emit matching documents. No scoring, no ranking—just membership (matches or doesn't match).

**Use case:** "Find all documents containing ('machine' AND 'learning') but NOT 'neural'. Give me the exact set of documents satisfying this logic."

---

## Scope

### In Scope ✓
- Boolean query parsing: AND, OR, NOT operators with parentheses
- Exact token matching (case-insensitive optional)
- Retrieve all documents matching Boolean expression
- Support multiple matching modes: all_tokens (AND), any_token (OR), require_term (NOT)
- Detailed output: which terms matched, which didn't, for each document
- Filtering before/after matching (stopwords, case normalization)
- Verbose mode: show query parse tree, matching logic
- Batch search: multiple queries against one corpus

### Out of Scope ✗
- Ranking: Boolean search is all-or-nothing (no scoring)
- Fuzzy matching: Exact token comparison only
- Phrase queries: No positional constraints (separate tool for phrases)
- Query optimization or simplification
- Relevance feedback
- Stemming/lemmatization (token comparison is exact)

---

## Module Structure

```
tools/boolean_search/
  __init__.py                     # exports main functions
  core.py                         # matching logic
  query_parser.py                 # parse Boolean expressions into AST
  evaluator.py                    # evaluate AST against corpus
  cli.py                          # argparse CLI
  search_schema.py                # dataclasses for input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `search_documents(corpus: list, query: str, config: dict = None) -> dict`

**Purpose:** Find all documents matching Boolean query expression.

**Input:**

- `corpus` (list): Documents with tokens:
  ```json
  [
    {
      "id": "doc_1",
      "tokens": ["machine", "learning", "algorithm"]
    },
    {
      "id": "doc_2",
      "tokens": ["deep", "learning", "neural", "network"]
    },
    {
      "id": "doc_3",
      "tokens": ["machine", "learning", "neural", "network"]
    }
  ]
  ```

- `query` (string): Boolean expression (infix notation):
  ```
  "machine AND learning"
  "(machine OR deep) AND learning"
  "machine AND learning NOT neural"
  "(machine OR deep) AND (learning AND NOT fake)"
  ```

- `config` (dict, optional):
  ```json
  {
    "lowercase": true,
    "remove_stopwords": false,
    "stopword_list": ["the", "a"],
    "verbose": false
  }
  ```

**Output:**

```json
{
  "tool": "boolean_search",
  "version": "v1",
  "run_id": "bool_search_001",
  "timestamp": "2026-07-14T15:10:00Z",
  "input_summary": {
    "corpus_size": 3,
    "query": "machine AND learning NOT neural"
  },
  "query_parse": {
    "ast": "AND(AND(machine, learning), NOT(neural))",
    "tokens": ["machine", "learning"],
    "negated_tokens": ["neural"],
    "valid": true
  },
  "results": [
    {
      "result_id": "doc_1",
      "rank": 1,
      "value": 1.0,
      "details": {
        "matches": true,
        "matched_tokens": ["machine", "learning"],
        "missing_tokens": [],
        "negated_present": [],
        "negated_absent": ["neural"],
        "token_coverage": 1.0
      }
    }
  ],
  "metadata": {
    "total_documents": 3,
    "matching_documents": 1,
    "match_ratio": 0.333,
    "computation_time_ms": 2
  }
}
```

#### 2. `parse_query(query: str) -> dict`

**Purpose:** Parse Boolean query into AST for inspection/debugging.

**Input:**
```json
{
  "query": "machine AND learning OR neural"
}
```

**Output:**
```json
{
  "query": "machine AND learning OR neural",
  "ast": "OR(AND(machine, learning), neural)",
  "tokens": ["machine", "learning", "neural"],
  "negated_tokens": [],
  "valid": true,
  "parse_errors": []
}
```

#### 3. `batch_search(corpus: list, queries: list, config: dict = None) -> dict`

**Purpose:** Execute multiple Boolean queries against one corpus.

**Input:**
```json
{
  "corpus": [...],
  "queries": [
    "machine AND learning",
    "neural AND learning NOT deep",
    "algorithm OR optimization"
  ],
  "config": {}
}
```

**Output:**
```json
{
  "batch_search_run_id": "batch_bool_001",
  "results": [
    {search_run_1},
    {search_run_2},
    {search_run_3}
  ],
  "summary": {
    "queries_executed": 3,
    "total_matches": 5,
    "average_match_ratio": 0.45
  }
}
```

---

## Boolean Query Syntax

### Operators

| Operator | Syntax | Meaning | Example |
|----------|--------|---------|---------|
| AND | `term1 AND term2` | Both terms must be present | `machine AND learning` |
| OR | `term1 OR term2` | At least one term must be present | `machine OR deep` |
| NOT | `NOT term` or `term1 NOT term2` | Exclude documents with term | `learning NOT fake` |
| Parens | `(expr)` | Override precedence | `(machine OR deep) AND learning` |

### Precedence (highest to lowest)

1. Parentheses `()`
2. NOT
3. AND
4. OR

### Examples

```
machine AND learning           → Docs with both "machine" and "learning"
machine OR deep                → Docs with "machine" or "deep" (or both)
machine NOT neural             → Docs with "machine" but not "neural"
(machine OR deep) AND learning → Docs with ("machine" OR "deep") AND "learning"
machine AND learning NOT neural AND NOT fake → Docs with both, excluding neural & fake
```

---

## Configuration Options

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens to lowercase
- `remove_stopwords` (bool, default false): Filter stopwords before matching
- `stopword_list` (array, default English): Custom stopwords
- `min_token_length` (int, default 1): Minimum token length to match
- `verbose` (bool, default false): Include query parse tree and matching logic

---

## CLI Interface

```bash
# Simple query
python -m tools.boolean_search \
  --input corpus.json \
  --query "machine AND learning" \
  --output results.json

# Complex query with parentheses
python -m tools.boolean_search \
  --input corpus.json \
  --query "(machine OR deep) AND learning NOT neural" \
  --output results.json

# Case-insensitive, with stopwords
python -m tools.boolean_search \
  --input corpus.json \
  --query "machine AND learning" \
  --lowercase \
  --remove-stopwords \
  --output results.json

# Verbose mode (show parse tree)
python -m tools.boolean_search \
  --input corpus.json \
  --query "machine AND learning" \
  --verbose \
  --output results.json

# Parse query only (no search)
python -m tools.boolean_search \
  --parse-only \
  --query "machine AND learning NOT neural"

# Batch search
python -m tools.boolean_search \
  --input corpus.json \
  --query-file queries.txt \
  --batch \
  --output results.json
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Corpus + Query):**
```json
{
  "corpus": [
    {"id": "doc_1", "tokens": [...]},
    {"id": "doc_2", "tokens": [...]}
  ],
  "query": "machine AND learning",
  "config": {}
}
```

**Shape B (Query only, with corpus from file):**
```json
{
  "corpus_file": "corpus.jsonl",
  "query": "machine AND learning"
}
```

### Output (JSON)

Standard Historical AI results format. Per-result details:
- `matches` (bool): Whether document satisfies query
- `matched_tokens` (array): Tokens in doc that matched query terms
- `missing_tokens` (array): Query terms NOT found in doc
- `negated_present` (array): Negated terms that ARE present (reason for non-match)
- `negated_absent` (array): Negated terms that are NOT present (good)
- `token_coverage` (float): Fraction of query terms found [0, 1]

---

## Algorithm Details

### Query Parsing

1. **Tokenize query:** Split on whitespace; recognize AND, OR, NOT, (, )
2. **Build AST:** Recursive descent parser respecting precedence
3. **Validate:** Check for syntax errors (mismatched parens, invalid operators)

### Query Evaluation

1. **Normalize corpus:** Apply config (lowercase, stopwords, min length) to all tokens
2. **Normalize query terms:** Apply same filters
3. **For each document:**
   - Evaluate AST recursively against doc token set
   - AND: both children must evaluate true
   - OR: at least one child must evaluate true
   - NOT: child must evaluate false
   - Term: term must be in doc's token set
4. **Return matching docs**

### Complexity

- **Time:** O(docs * avg_tokens * query_complexity) ≈ O(N) for typical queries
- **Space:** O(query_size) for AST

---

## Edge Cases & Error Handling

1. **Empty query string:** Exit 1 (ValueError)
2. **Malformed query (mismatched parens, invalid operator):** Exit 1 (ValueError) with parse error
3. **Query term not in corpus:** Term evaluates false for all docs (no error)
4. **Empty corpus:** Return empty results (no error)
5. **Duplicate terms in query:** Treated as single term (e.g., `machine AND machine` = `machine`)
6. **Case sensitivity:** Handled by config (lowercase normalization)
7. **Stopword filtering:** Applied before matching if config specifies

---

## Testing Strategy

### Explicit Test Cases (TEST-boolean_search_examples.json)

1. **Simple AND:**
   - Query: `"machine AND learning"`
   - Docs: [has both, has one, has neither]
   - Expected: Only doc with both matches

2. **OR logic:**
   - Query: `"machine OR deep"`
   - Docs: [has machine, has deep, has both, has neither]
   - Expected: First 3 match

3. **NOT logic:**
   - Query: `"machine NOT neural"`
   - Expected: Docs with machine but not neural match

4. **Complex precedence:**
   - Query: `"(machine OR deep) AND learning"`
   - Expected: Docs with (machine or deep) AND learning match

5. **Malformed query:**
   - Query: `"machine AND (learning"`
   - Expected: Exit 1, parse error

6. **Case normalization:**
   - Query: `"Machine AND LEARNING"` with lowercase=true
   - Expected: Matches "machine" and "learning" tokens

7. **Stopword filtering:**
   - Query: `"the machine AND learning"` with remove_stopwords=true
   - Expected: "the" ignored; search for machine AND learning

---

## Performance Notes

- **Typical:** 1000 docs, 100 tokens each, simple query → <10ms
- **Scales:** Linear with corpus size
- **Bottleneck:** None (very fast; dominated by I/O)
- **Cache opportunity:** Tokenized corpus can be pre-filtered (v2)

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, re, collections
- **External libs:** None (stdlib only)
- **Resource limits:** Max 100K docs, 1M tokens total
- **Hardware:** CPU-only

---

## Related Tools

- **TF-IDF Ranker v1:** Scoring-based ranking (complementary)
- **Text Search v1:** Simple pattern matching (different algorithm)
- **Inverted Index Builder v1:** Can support faster boolean search (v2)
- **Tokenizer v1:** Pre-processes text (upstream)

---

## Non-Goals

- **Ranking:** Boolean search is binary (match or not)
- **Scoring:** No relevance computation
- **Phrase queries:** Positional constraints not supported
- **Query expansion:** No synonyms or related terms
- **Learning:** No training or model building

---

## Post-1.0 Extensions

1. **Inverted index support:** Pre-computed index for faster matching on large corpora
2. **Phrase queries:** Support `"exact phrase"` as single term
3. **Wildcard matching:** `machine*` matches machine, machines, machinery
4. **Range queries:** Date ranges, numeric comparisons
5. **Query optimization:** Simplify redundant expressions (e.g., `machine AND machine` → `machine`)

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, TOOL_PHILOSOPHY.md
