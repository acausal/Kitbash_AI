# SPEC: Trie/Prefix Tree v1

**Module:** `tools/trie/`  
**Status:** Ready for build  
**Dependencies:** stdlib (json, collections)  
**Priority:** Medium (command completion, query routing optimization, fast negation pattern detection)

---

## Overview

Build and query a trie (prefix tree) data structure for fast prefix-based lookups and pattern matching. Support standard trie operations (insert, search, prefix matching) plus optional negation patterns (exclude terms starting with specific prefixes). Useful for: command completion, query routing, fast lexicon lookups, negation-aware search.

**Design principle:** Deterministic trie implementation using nested dicts. No external libraries. Support both read-only (query-only) and mutable (build) modes. Output is JSON-serializable for persistence.

**Use case:** "I have a vocabulary of 10K grain names and query terms. Build a trie. User types 'photo' → find all matching completions instantly. User types '!photo' → find all terms NOT starting with 'photo'."

---

## Scope

### In Scope ✓
- Build trie from list of strings
- Query operations: exact match, prefix search (all strings with prefix), autocomplete/suggestions
- Negation patterns: exclude terms matching prefix patterns (NOT "photo" → exclude "photosynthesis", "photo-oxidation")
- Wildcard support: trailing `*` to denote prefix search (optional; explicit parameter preferred)
- Trie serialization/deserialization to JSON (persistence)
- Statistics: trie size, depth, node count, vocabulary stats
- Case sensitivity: configurable (default: preserve case, case-sensitive queries)
- Output: JSON with matches + metadata

### Out of Scope ✗
- Fuzzy matching or edit distance (separate tool)
- Regex patterns (use Boolean Search tool)
- Weights or ranking (separate tool)
- Dynamic deletion (v1 is write-once; rebuild to delete)
- Suffix trees or suffix arrays (different data structure)
- Multi-language support (v1 is language-agnostic, assumes UTF-8)

---

## Module Structure

```
tools/trie/
  __init__.py                    # exports main functions
  core.py                        # trie building and querying
  trie_node.py                   # TrieNode dataclass
  negation.py                    # negation pattern handling
  serialization.py               # JSON persist/load
  cli.py                         # argparse CLI
  trie_schema.py                 # dataclasses for JSON output
  README.md                       # usage docs + examples
  __main__.py                    # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

All functions accept/return JSON-serializable types (strings, dicts, lists).

#### 1. `build_trie(vocabulary: list, case_sensitive: bool = True) -> dict`

**Purpose:** Build a trie from a vocabulary list.

**Input:**
- `vocabulary` (list): List of strings to insert into trie
  ```json
  [
    "photosynthesis",
    "photorespiration",
    "photo-oxidation",
    "chlorophyll",
    "respiration",
    "ATP"
  ]
  ```

- `case_sensitive` (bool): If True, treat 'Photo' and 'photo' as different (default: True)

**Output (JSON):**
```json
{
  "build_params": {
    "vocabulary_size": 6,
    "case_sensitive": true
  },
  "trie_stats": {
    "node_count": 34,
    "trie_depth": 15,
    "avg_branch_factor": 1.2,
    "vocabulary_retained": 6
  },
  "trie": {
    "root": {
      "p": {
        "h": {
          "o": {
            "t": {
              "o": {
                "s": {
                  "y": { ... }
                },
                "r": { ... },
                "-": { ... }
              }
            }
          }
        }
      },
      "c": { ... },
      "r": { ... },
      "A": { ... }
    }
  },
  "metadata": {
    "timestamp_built": "2026-07-14T15:00:00Z",
    "vocabulary_sample": ["photosynthesis", "photorespiration", "chlorophyll"],
    "completeness": 1.0
  }
}
```

**Behavior:**
- Insert each vocabulary string into trie character by character
- Mark terminal nodes (end of word) with special marker
- Optionally case-normalize if case_sensitive=False
- Return trie structure (nested dicts) + metadata

**Error handling:**
- `ValueError` if vocabulary is empty
- `ValueError` if vocabulary contains non-strings
- `ValueError` if vocabulary contains empty strings

---

#### 2. `search_trie(trie: dict, query: str, case_sensitive: bool = True) -> dict`

**Purpose:** Exact match search in trie.

**Input:**
- `trie` (dict): Trie structure from build_trie()
- `query` (str): Term to search for (e.g., "photosynthesis")
- `case_sensitive` (bool): Match case_sensitive setting used in build

**Output (JSON):**
```json
{
  "query": "photosynthesis",
  "case_sensitive": true,
  "found": true,
  "path_traversed": "p→h→o→t→o→s→y→n→t→h→e→s→i→s",
  "is_terminal": true,
  "statistics": {
    "depth_traversed": 15,
    "nodes_visited": 15,
    "trie_size": 34
  }
}
```

**Behavior:**
- Traverse trie following query characters
- Return true if path terminates (word exists in vocabulary)
- Return false if path breaks (word not found)

**Error handling:**
- `ValueError` if query is empty
- `ValueError` if trie structure invalid

---

#### 3. `prefix_search(trie: dict, prefix: str, case_sensitive: bool = True, max_results: int = None) -> dict`

**Purpose:** Find all vocabulary terms with given prefix.

**Input:**
- `trie` (dict): Trie structure
- `prefix` (str): Prefix to search for (e.g., "photo")
- `case_sensitive` (bool): Match case setting
- `max_results` (int, optional): Limit results (default: None = all)

**Output (JSON):**
```json
{
  "prefix": "photo",
  "case_sensitive": true,
  "matches": [
    "photosynthesis",
    "photorespiration",
    "photo-oxidation"
  ],
  "match_count": 3,
  "truncated": false,
  "statistics": {
    "depth_at_prefix_end": 5,
    "subtree_size": 8,
    "search_time_estimate_ns": 1200
  }
}
```

**Behavior:**
- Traverse trie to prefix endpoint
- Depth-first search (DFS) from that point to collect all terminal nodes
- Return all matching vocabulary terms
- Truncate results if max_results exceeded (flag truncation)

**Error handling:**
- `ValueError` if prefix is empty
- `ValueError` if prefix not found in trie (return empty matches, not error)

---

#### 4. `suggest_completions(trie: dict, prefix: str, case_sensitive: bool = True, max_suggestions: int = 10) -> dict`

**Purpose:** Autocomplete: find suggestions for partial input.

**Input:**
- `trie` (dict): Trie structure
- `prefix` (str): Partial user input (e.g., "pho")
- `case_sensitive` (bool): Match case setting
- `max_suggestions` (int): Max suggestions to return (default: 10)

**Output (JSON):**
```json
{
  "user_input": "pho",
  "case_sensitive": true,
  "suggestions": [
    {
      "rank": 1,
      "completion": "photosynthesis",
      "suffix": "tosynthesis",
      "confidence": 1.0
    },
    {
      "rank": 2,
      "completion": "photorespiration",
      "suffix": "torespiration",
      "confidence": 1.0
    },
    {
      "rank": 3,
      "completion": "photo-oxidation",
      "suffix": "to-oxidation",
      "confidence": 1.0
    }
  ],
  "suggestion_count": 3,
  "statistics": {
    "prefix_unique": true,
    "avg_suggestion_length": 15
  }
}
```

**Behavior:**
- Call prefix_search() under the hood
- Return matches as suggestions (completion + suffix to append)
- Rank by vocabulary order (first inserted = rank 1)
- Truncate if needed

**Error handling:**
- `ValueError` if prefix empty
- Graceful return of empty suggestions if prefix not found

---

#### 5. `negation_search(trie: dict, patterns: list, case_sensitive: bool = True, max_results: int = None) -> dict`

**Purpose:** Find vocabulary terms that do NOT match negation patterns.

**Input:**
- `trie` (dict): Trie structure
- `patterns` (list): List of prefixes/patterns to exclude (no leading '!')
  ```json
  ["photo", "atp"]
  ```

- `case_sensitive` (bool): Match case setting
- `max_results` (int, optional): Limit results

**Output (JSON):**
```json
{
  "negation_patterns": ["photo", "atp"],
  "case_sensitive": true,
  "excluded_prefixes": ["photo", "atp"],
  "all_terms": 6,
  "excluded_terms": 3,
  "included_terms": [
    "chlorophyll",
    "respiration"
  ],
  "included_count": 2,
  "statistics": {
    "exclusion_rate": 0.5,
    "included_sample": ["chlorophyll", "respiration"]
  }
}
```

**Behavior:**
- Get all vocabulary terms (full DFS)
- Filter out terms matching any negation pattern prefix
- Return remaining terms

**Error handling:**
- `ValueError` if patterns is empty (no-op, return all terms)
- `ValueError` if any pattern is invalid

---

#### 6. `get_trie_stats(trie: dict) -> dict`

**Purpose:** Compute statistics about trie structure.

**Input:**
- `trie` (dict): Trie structure

**Output (JSON):**
```json
{
  "trie_statistics": {
    "node_count": 34,
    "max_depth": 15,
    "min_depth": 3,
    "avg_depth": 9.2,
    "vocabulary_size": 6,
    "branch_factor_max": 3,
    "branch_factor_avg": 1.2,
    "branching_nodes": 8,
    "leaf_nodes": 6,
    "internal_nodes": 22
  },
  "memory_estimate_bytes": 4800,
  "sparsity": 0.18,
  "size_interpretation": "compact"
}
```

**Behavior:**
- Traverse entire trie and collect statistics
- Compute tree metrics (depth, branching)
- Estimate memory footprint

**Error handling:**
- `ValueError` if trie structure invalid

---

#### 7. `serialize_trie(trie: dict) -> dict`

**Purpose:** Convert trie to JSON-serializable format (already done if using build_trie output).

**Input:**
- `trie` (dict): Trie structure

**Output (JSON):**
```json
{
  "trie_json": { /* nested dict representation */ },
  "serialization_params": {
    "format": "nested_dict",
    "encodable": true
  }
}
```

**Behavior:**
- Ensure trie is JSON-serializable (should already be if built from build_trie)
- Optionally compress/optimize (v1: no compression)

---

#### 8. `deserialize_trie(trie_json: str) -> dict`

**Purpose:** Load trie from JSON string.

**Input:**
- `trie_json` (str): JSON string from serialize_trie output

**Output (JSON):**
```json
{
  "trie": { /* loaded trie */ },
  "validation": {
    "valid": true,
    "node_count": 34,
    "vocabulary_retained": 6
  }
}
```

**Behavior:**
- Parse JSON string
- Validate trie structure
- Return loaded trie

**Error handling:**
- `ValueError` if JSON invalid
- `ValueError` if trie structure invalid after load

---

### CLI Interface (in `cli.py`)

```bash
# Build trie from vocabulary file
python -m tools.trie build \
  --vocabulary vocab.jsonl \
  --case-sensitive \
  --output trie.json

# Search exact match
python -m tools.trie search \
  --trie trie.json \
  --query "photosynthesis"

# Prefix search
python -m tools.trie prefix-search \
  --trie trie.json \
  --prefix "photo" \
  --max-results 10

# Autocomplete suggestions
python -m tools.trie suggest \
  --trie trie.json \
  --input "pho" \
  --max-suggestions 5

# Negation search (exclude patterns)
python -m tools.trie negation-search \
  --trie trie.json \
  --exclude-patterns '["photo", "atp"]' \
  --max-results 100

# Get trie statistics
python -m tools.trie stats \
  --trie trie.json

# Save/load trie
python -m tools.trie save \
  --trie trie.json \
  --output saved_trie.json

python -m tools.trie load \
  --trie-file saved_trie.json
```

**Output:** JSON to stdout

**Exit codes:**
- `0`: Success
- `1`: ValueError (invalid input)
- `2`: RuntimeError (I/O or structural error)

---

## Use Cases & Workflows

### 1. Command Completion (REPL/agent)

```
User input: "cart"
↓ suggest_completions(trie, "cart", max_suggestions=5)
Suggestions:
  1. cartridge
  2. cartridge_loader
  3. cartridges
  4. cart_analysis
  5. cartesian_product

User picks #1 → "cartridge" sent to orchestrator
```

### 2. Query Routing Optimization

```
Query: "photo*" (user-entered wildcard)
↓ prefix_search(trie, "photo")
Matches: [photosynthesis, photorespiration, photo-oxidation]
→ Route query to all 3 grains in parallel
→ Faster than checking all 10K grains
```

### 3. Negation-Aware Query

```
User: "Find topics about energy NOT related to photosynthesis"
↓ negation_search(trie, patterns=["photo"])
Excluded: [photosynthesis, photorespiration, photo-oxidation]
Included: [respiration, ATP, cellular_respiration, energy_transfer]
→ Search corpus excluding photosynthesis-related terms
```

### 4. Grain Name Lookup

```
Query: "Is 'photosyn' a complete grain name?"
↓ search_trie(trie, "photosyn") → found=False
→ Suggest completions: "photosynthesis", "photorespiration"
```

---

## Data Flow Example

```
Sleep Stage 1 aggregates all grain names:
  grains = [grain_42, grain_137, grain_89, ..., grain_10000]

↓ trie.build_trie(grains)

Trie built, statistics:
  - 10,000 vocabulary size
  - 45,000 nodes
  - max depth 20
  - memory ~6MB

Query Orchestrator asks: "Which grains start with 'query'?"
↓ prefix_search(trie, "query_*")
Result: [query_router_A, query_router_B, query_classifier_C] (3 matches)
→ Route efficiently

Stage 5 during procedural edge extraction:
  User wants "all grains EXCEPT those related to routing"
↓ negation_search(trie, patterns=["query_", "route_"])
Result: [fact_retriever, kb_lookup, consolidator, ...]
→ Analyze non-routing reasoning chains
```

---

## Testing Strategy

### Test Cases

1. **Build trie from vocabulary:**
   - Vocabulary: ["cat", "car", "card", "dog"]
   - Expected: 4 terminal nodes, ~8 internal nodes

2. **Exact match search:**
   - Query: "car" → found=True
   - Query: "ca" → found=False

3. **Prefix search:**
   - Prefix: "ca" → matches ["cat", "car", "card"]
   - Prefix: "do" → matches ["dog"]
   - Prefix: "xyz" → matches []

4. **Autocomplete:**
   - Input: "ca" → suggestions ["cat", "car", "card"]
   - Input: "card" → suggestions ["card"]

5. **Negation search:**
   - Exclude: ["ca"] → matches ["dog"]
   - Exclude: ["cat", "dog"] → matches ["car", "card"]

6. **Case sensitivity:**
   - Build with case_sensitive=True
   - Query "Cat" (uppercase) vs "cat" (lowercase) → different results
   - Build with case_sensitive=False
   - Query "Cat" vs "cat" → same results

7. **Trie stats:**
   - Small vocabulary → reasonable node count
   - Deep vocabulary ("aaa...aaab") → high max depth

8. **Serialization round-trip:**
   - Build → serialize → deserialize → query
   - Results should match original trie

### Example Test File (TEST-trie_examples.json)

```json
{
  "test_cases": [
    {
      "name": "build_trie_simple",
      "function": "build_trie",
      "input": {
        "vocabulary": ["photosynthesis", "photorespiration", "photo-oxidation", "chlorophyll", "respiration", "ATP"],
        "case_sensitive": true
      },
      "expected_output": {
        "vocabulary_size": 6,
        "node_count_min": 30,
        "trie_depth_min": 10
      }
    },
    {
      "name": "search_exact_match_found",
      "function": "search_trie",
      "input": {
        "query": "photosynthesis",
        "case_sensitive": true
      },
      "expected_output": {
        "found": true,
        "is_terminal": true
      }
    },
    {
      "name": "search_exact_match_not_found",
      "function": "search_trie",
      "input": {
        "query": "photo",
        "case_sensitive": true
      },
      "expected_output": {
        "found": false
      }
    },
    {
      "name": "prefix_search_photo",
      "function": "prefix_search",
      "input": {
        "prefix": "photo",
        "case_sensitive": true
      },
      "expected_output": {
        "matches": ["photosynthesis", "photorespiration", "photo-oxidation"],
        "match_count": 3
      }
    },
    {
      "name": "prefix_search_no_matches",
      "function": "prefix_search",
      "input": {
        "prefix": "xyz",
        "case_sensitive": true
      },
      "expected_output": {
        "match_count": 0
      }
    },
    {
      "name": "suggest_completions",
      "function": "suggest_completions",
      "input": {
        "prefix": "pho",
        "max_suggestions": 5
      },
      "expected_output": {
        "suggestions_count_min": 3,
        "suggestions_count_max": 3,
        "rank_1_completion": "photosynthesis"
      }
    },
    {
      "name": "negation_search",
      "function": "negation_search",
      "input": {
        "patterns": ["photo", "atp"],
        "case_sensitive": true
      },
      "expected_output": {
        "excluded_count": 4,
        "included_count": 2,
        "included_terms_include": ["chlorophyll", "respiration"]
      }
    },
    {
      "name": "case_sensitivity",
      "function": "prefix_search",
      "input": {
        "prefix": "Photo",
        "case_sensitive": true
      },
      "expected_output": {
        "match_count": 0
      }
    }
  ]
}
```

---

## Negation Details

**Negation Pattern Syntax:**
- Prefix-based only: "photo" means exclude all terms starting with "photo"
- No regex or wildcards (use Boolean Search tool for complex patterns)
- Case-sensitive/insensitive matching follows trie's case_sensitive setting
- Multiple patterns are OR'ed: exclude pattern_A OR pattern_B OR pattern_C

**Negation Use Cases:**
1. Query exclusion: "find X but not Y"
2. Grain filtering: "analyze all grains except routing/search components"
3. Vocabulary filtering: "all terms except deprecated ones"

---

## Non-Goals

- ❌ Fuzzy matching or typo correction (separate tool)
- ❌ Regex patterns (Boolean Search tool)
- ❌ Dynamic deletion/updates (write-once; rebuild to modify)
- ❌ Ranking or weighting (separate tool)
- ❌ Suffix trees (different data structure)
- ❌ Multi-language normalization (v1: UTF-8 agnostic)

---

## Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| stdlib | — | json, collections | No external deps |

**No external libraries needed. Pure Python stdlib.**

---

## Future Enhancements (Post-1.0)

1. **v1.1: Weighted suggestions** — Rank completions by frequency
2. **v1.2: Dynamic deletion** — Remove vocabulary items (rebuild internally)
3. **v2.0: Fuzzy prefix matching** — Levenshtein distance on prefixes
4. **v2.0: Trie compression** — Radix tree (compressed trie)
5. **v2.1: Multi-key trie** — Support tuples or composite keys

---

**Last updated:** 2026-07-14  
**Author:** Isaac (Kitbash AI)  
**For:** tools/ ecosystem, query routing, autocomplete, grain name lookup  
**Related:** BOOLEAN_SEARCH_SPEC.md, TEXT_SEARCH_SPEC.md
