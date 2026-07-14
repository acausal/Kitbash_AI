# SPEC: Markov Chain v1

**Module:** `tools/markov_chain/`  
**Status:** Ready for spec  
**Dependencies:** stdlib (json, collections, random, itertools)  
**Priority:** Medium (sequence modeling, text generation, pattern analysis)

---

## Overview

Build and query Markov chains (n-gram transition tables) from token sequences. Deterministic model construction: no learning phase, no persistent state. All computation from pre-tokenized input. Generate new sequences or analyze transition probabilities from existing tokens.

**Design principle:** Stateless chain construction. Accept token stream; emit n-gram transition probabilities in JSON. Use seeded randomness for reproducible generation (same seed → same output). Chain can be queried or used to generate text.

**Use case:** "I have execution traces (tool sequences). Build me a Markov chain to model transitions. Show me: what tools usually follow 'tokenizer'? Generate a plausible sequence starting with 'tokenizer'."

---

## Scope

### In Scope ✓
- Build Markov chains from token sequences: configurable order (1-grams, 2-grams, 3-grams, etc.)
- Compute transition probabilities: next token given current state
- Query chain: "What tokens follow this state? With what probabilities?"
- Generate sequences: sample from chain using seeded RNG for reproducibility
- Support multiple order chains simultaneously (analyze 1-gram + 2-gram + 3-gram patterns)
- Detailed output: transition counts, probabilities, entropy/randomness estimates
- Batch processing: build chains from multiple corpora

### Out of Scope ✗
- Smoothing/backoff strategies: Use observed frequencies only (v1)
- Language-specific tuning: No grammar, parsing, or linguistic features
- Prediction with confidence intervals: Chain gives probabilities only
- Learning or parameter optimization
- Real-time sequence analysis (streaming)
- Multi-layer or hierarchical Markov models

---

## Module Structure

```
tools/markov_chain/
  __init__.py                     # exports main functions
  core.py                         # chain building and querying
  generation.py                   # sequence generation with seeded RNG
  cli.py                          # argparse CLI
  chain_schema.py                 # dataclasses for input/output
  README.md                        # usage + examples
  __main__.py                     # CLI entry point
```

---

## API

### Core Functions (in `core.py`)

#### 1. `build_markov_chain(tokens: list, order: int = 2, case_sensitive: bool = True) -> dict`

**Purpose:** Build Markov chain from token sequence.

**Input:**

- `tokens` (list): Sequence of tokens:
  ```json
  ["tokenizer", "negation_detector", "svo_extractor", "json_filter", "tokenizer", "text_search"]
  ```

- `order` (int, default 2): N-gram order (1 = unigrams, 2 = bigrams, 3 = trigrams)
- `case_sensitive` (bool, default true): Normalize token case

**Output:**

```json
{
  "tool": "markov_chain",
  "version": "v1",
  "run_id": "markov_001",
  "timestamp": "2026-07-14T15:25:00Z",
  "input_summary": {
    "token_count": 6,
    "unique_tokens": 5,
    "order": 2
  },
  "chain": {
    "order": 2,
    "state_count": 5,
    "transition_count": 5,
    "states": {
      "tokenizer": {
        "transitions": {
          "negation_detector": {
            "count": 1,
            "probability": 0.5
          },
          "text_search": {
            "count": 1,
            "probability": 0.5
          }
        },
        "total_transitions": 2,
        "entropy": 1.0
      },
      "negation_detector": {
        "transitions": {
          "svo_extractor": {
            "count": 1,
            "probability": 1.0
          }
        },
        "total_transitions": 1,
        "entropy": 0.0
      },
      "svo_extractor": {
        "transitions": {
          "json_filter": {
            "count": 1,
            "probability": 1.0
          }
        },
        "total_transitions": 1,
        "entropy": 0.0
      },
      "json_filter": {
        "transitions": {
          "tokenizer": {
            "count": 1,
            "probability": 1.0
          }
        },
        "total_transitions": 1,
        "entropy": 0.0
      }
    }
  },
  "metadata": {
    "computation_time_ms": 3,
    "config_used": {
      "order": 2,
      "case_sensitive": true
    }
  }
}
```

#### 2. `generate_sequence(chain: dict, start_token: str = None, length: int = 10, seed: int = None) -> dict`

**Purpose:** Generate token sequence from Markov chain (reproducible with seeded RNG).

**Input:**

- `chain` (dict): Built chain from `build_markov_chain`
- `start_token` (str, optional): Starting token (random if null)
- `length` (int, default 10): Length of sequence to generate
- `seed` (int, optional): Random seed for reproducibility (if null, use unseeded RNG but still deterministic)

**Output:**

```json
{
  "tool": "markov_chain",
  "version": "v1",
  "run_id": "markov_gen_001",
  "timestamp": "2026-07-14T15:25:05Z",
  "generation": {
    "chain_order": 2,
    "start_token": "tokenizer",
    "sequence_length": 10,
    "generated_sequence": [
      "tokenizer",
      "negation_detector",
      "svo_extractor",
      "json_filter",
      "tokenizer",
      "text_search",
      "tokenizer",
      "negation_detector",
      "svo_extractor",
      "json_filter"
    ],
    "completed": true,
    "termination_reason": "length_reached",
    "seed_used": 42
  },
  "metadata": {
    "computation_time_ms": 2,
    "generation_stats": {
      "mean_entropy": 0.4,
      "min_entropy_state": "svo_extractor",
      "max_entropy_state": "tokenizer"
    }
  }
}
```

#### 3. `query_chain(chain: dict, state: str) -> dict`

**Purpose:** Query transition probabilities for a given state.

**Input:**

```json
{
  "chain": {... built chain ...},
  "state": "tokenizer"
}
```

**Output:**

```json
{
  "state": "tokenizer",
  "found": true,
  "transitions": {
    "negation_detector": {
      "count": 1,
      "probability": 0.5
    },
    "text_search": {
      "count": 1,
      "probability": 0.5
    }
  },
  "total_transitions": 2,
  "entropy": 1.0
}
```

#### 4. `build_multi_order_chain(tokens: list, orders: list = [1, 2, 3]) -> dict`

**Purpose:** Build multiple order chains simultaneously for comparison.

**Input:**

- `tokens` (list): Token sequence
- `orders` (list, default [1, 2, 3]): List of orders to build

**Output:**

```json
{
  "chains": [
    {... chain for order 1 ...},
    {... chain for order 2 ...},
    {... chain for order 3 ...}
  ],
  "summary": {
    "orders_built": [1, 2, 3],
    "total_states": [5, 5, 4],
    "total_transitions": [5, 5, 3]
  }
}
```

---

## Markov Chain Format

### Standard Structure

```json
{
  "order": int,
  "state_count": int,
  "transition_count": int,
  "states": {
    "state_name": {
      "transitions": {
        "next_token": {
          "count": int,
          "probability": float [0, 1]
        }
      },
      "total_transitions": int,
      "entropy": float
    }
  }
}
```

### Terminology

- **State:** Current n-gram (order 1 = single token, order 2 = token pair, etc.)
- **Transition:** Possible next token after current state
- **Count:** Number of times this transition observed in input
- **Probability:** count / total_transitions for this state
- **Entropy:** Shannon entropy of transition probabilities (0 = deterministic, ~1 = uniform)

### Entropy Calculation

For a state with transition probabilities p₁, p₂, ..., pₙ:
```
entropy = -Σ(pᵢ * log₂(pᵢ))  [for pᵢ > 0]
```

Range: [0, log₂(n)] where n = number of possible transitions
- entropy ≈ 0: Deterministic (one likely successor)
- entropy ≈ 1: Uniform (all successors equally likely)

---

## Configuration & Parameters

### Standard Config (Shared Contract)
- `lowercase` (bool, default true): Normalize tokens
- `verbose` (bool, default false): Include detailed stats

### Markov Specific
- `order` (int, default 2): N-gram order (1–5 recommended)
- `case_sensitive` (bool, default true): Token case handling
- `min_occurrence` (int, default 1): Minimum transition count to include (for filtering rare transitions)

---

## CLI Interface

```bash
# Build chain
python -m tools.markov_chain \
  --input tokens.json \
  --order 2 \
  --output chain.json

# Query chain
python -m tools.markov_chain \
  --chain chain.json \
  --query-state tokenizer

# Generate sequence
python -m tools.markov_chain \
  --chain chain.json \
  --generate \
  --start-token tokenizer \
  --length 10 \
  --seed 42 \
  --output generated.json

# Build multiple orders
python -m tools.markov_chain \
  --input tokens.json \
  --orders 1,2,3 \
  --output chains_multi.json

# Verbose mode
python -m tools.markov_chain \
  --input tokens.json \
  --order 2 \
  --verbose \
  --output chain.json
```

---

## Input/Output Formats

### Input (JSON)

**Shape A (Tokens + Config):**
```json
{
  "tokens": ["token1", "token2", "token3", ...],
  "config": {
    "order": 2,
    "case_sensitive": true
  }
}
```

**Shape B (Generation):**
```json
{
  "chain": {... built chain ...},
  "start_token": "tokenizer",
  "length": 10,
  "seed": 42
}
```

### Output (JSON)

Standard Historical AI results format. Chain data in `chain` field with `states` dictionary.

---

## Algorithm Details

### Chain Construction

1. **Validate order:** 1 ≤ order ≤ token_count
2. **Generate n-grams:** Extract all overlapping sequences of length (order + 1)
   - First `order` tokens = state
   - Last token = next transition
3. **Count transitions:** For each n-gram, increment (state → next_token) count
4. **Compute probabilities:** For each state, prob(next) = count(next) / sum(all transitions)
5. **Compute entropy:** Shannon entropy of probabilities for each state

### Sequence Generation

1. **Initialize:** Start with start_token (or random token from chain)
2. **For each step (up to `length`):**
   - Look up current state in chain
   - Sample next token from transition distribution (seeded RNG)
   - Append to generated sequence
   - Update current state
3. **Emit:** Sequence with metadata

### Complexity

- **Time (build):** O(token_count * order) for n-gram generation + counting
- **Time (generate):** O(sequence_length * avg_transitions_per_state)
- **Space:** O(vocabulary_size + total_transitions)

---

## Edge Cases & Error Handling

1. **Order > token_count:** Exit 1 (ValueError)
2. **Empty tokens:** Return empty chain (no error)
3. **Start token not in chain:** Exit 1 (ValueError) for generation
4. **Unobserved transition during generation:** Terminate sequence early; emit `completed: false`, `termination_reason: "dead_end"`
5. **Single unique token:** All transitions point to itself; entropy = 0
6. **Duplicate n-grams:** Count each occurrence; probabilities reflect frequency

---

## Testing Strategy

### Explicit Test Cases (TEST-markov_chain_examples.json)

1. **Simple chain (order 2):**
   - 6 tokens with known transitions
   - Expected: Correct probability distribution for each state

2. **Entropy calculation:**
   - State with 1 transition (deterministic): entropy ≈ 0
   - State with 2 equal transitions: entropy ≈ 1

3. **Generation reproducibility:**
   - Generate twice with same seed
   - Expected: Identical sequences

4. **Multi-order chains:**
   - Build orders 1, 2, 3 from same token sequence
   - Expected: Different state/transition counts per order

5. **Order=1 (unigrams):**
   - Build unigram chain
   - Expected: States are single tokens; transitions are next tokens

6. **Dead-end handling:**
   - Generate from state with no outgoing transitions
   - Expected: Terminate early with `completed: false`

7. **Single unique token:**
   - Tokens: ["token", "token", "token"]
   - Expected: One state, one transition (to itself), entropy = 0

---

## Performance Notes

- **Typical:** 10K token sequence, order 2 → <50ms
- **Scales:** Linear with token count
- **Generation:** Fast (exponential in sequence length, but typically small)
- **Memory:** O(vocabulary_size) for state table

---

## Dependencies & Constraints

- **Python:** 3.8+
- **Imports:** json, collections, random, itertools, math
- **External libs:** None (stdlib only)
- **Resource limits:** Max 1M tokens, order ≤ 10
- **Hardware:** CPU-only

---

## Related Tools

- **Tokenizer v1:** Pre-processes text (upstream)
- **Sequence Pattern Miner v1:** Discovers patterns (complementary)
- **Frequency Analysis v1:** Computes unigram frequencies (related)

---

## Non-Goals

- **Smoothing:** No Laplace/Kneser-Ney smoothing (v1)
- **Language modeling:** Not a full language model (no perplexity metrics, no OOV handling)
- **Context beyond order:** Only immediate n-gram context (no long-range dependencies)
- **Learning or parameter optimization**
- **Semantic awareness:** Pure syntactic token transitions

---

## Post-1.0 Extensions

1. **Backoff smoothing:** Handle unobserved transitions via backoff to lower orders
2. **Variable-order chains:** Adapt order based on context (order 3 for high-entropy states, order 1 for deterministic)
3. **Conditional Markov chains:** Chain conditioned on metadata (e.g., "transitions only for successful traces")
4. **Perplexity scoring:** Evaluate how well chain explains held-out sequences
5. **Chain merging:** Combine chains from multiple corpora

---

**Last updated:** 2026-07-14  
**For:** Historical AI batch  
**Related:** Historical AI Shared Contract v1, Sequence Pattern Miner v1, Frequency Analysis v1
