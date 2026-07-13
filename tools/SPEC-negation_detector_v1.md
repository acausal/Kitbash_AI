# SPEC: Negation Detector v1

## Purpose
Detect negation in text and mark negated tokens. Identifies negation markers ("not", "no", "never", etc.) and tags nearby tokens as negated. Designed to integrate with tokenizer (takes raw text, outputs enriched tokens with negation info). v1 uses simple pattern matching; linguistic scope analysis deferred to v2+.

## Scope

### In Scope
- Accept raw text input
- Identify negation markers (hardcoded list: "not", "no", "never", "neither", "nor", "don't", "doesn't", "didn't", "won't", "can't", "couldn't", "shouldn't", "wouldn't", etc.)
- Mark tokens within a window (default: 5 tokens) of a negation marker as negated
- Return enriched tokens with `is_negated` flag
- CLI entry point: `python -m tools.negation_detector <input.txt> [--window <N>]`
- Library API: `detect_negations(text: str, window: int = 5) -> List[Token]`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Linguistic scope analysis (figure out what negation *applies to*)
- Multi-word negations ("in no way")
- Negation of negation (double negatives)
- Domain-specific negation patterns (medical, legal, etc.)
- Interaction with tokenizer (assume raw text input; tokenize internally if needed)

## Data Structures

### Token (reuse from tokenizer)
Same `Token` dataclass, with one addition:
```python
@dataclass
class Token:
    text: str              # Original token text
    lemma: str             # Base form
    pos: str               # Part of speech
    is_stop: bool          # Is this a stop word?
    is_punct: bool         # Is this punctuation?
    is_space: bool         # Is this whitespace?
    idx: int               # Character offset in original text
    doc_idx: int           # Index in token sequence
    is_negated: bool       # NEW: Is this token negated?
```

## API Contract

### Library API
```python
from tools.negation_detector import detect_negations

tokens = detect_negations("I don't like this")
# Returns tokens with is_negated=True for tokens near "don't"

tokens = detect_negations("I don't like this", window=3)
# Smaller window (default is 5)
```

**Signature:**
```python
def detect_negations(text: str, window: int = 5) -> List[Token]:
    """
    Detect negation in text and mark negated tokens.
    
    Args:
        text: Raw input text
        window: Token window around negation marker to mark as negated (default: 5)
    
    Returns:
        List of Token objects with is_negated flag set
    
    Raises:
        ValueError: Text is None or not a string
        ValueError: Window is not a positive integer
    """
```

### CLI
```bash
python -m tools.negation_detector input.txt
python -m tools.negation_detector input.txt --window 3
python -m tools.negation_detector input.txt -w 3
```

**Behavior:**
- Read input text from file
- Detect negations (default window: 5 tokens)
- Output JSON array of Token objects (with is_negated flag)
- Exit code 0 on success, 1 on failure
- Print summary to stdout: `Detected negations in <input> → <N> tokens, <K> marked as negated`

**Output format (JSON):**
```json
{
  "tokens": [
    {"text": "I", "lemma": "I", "pos": "PRON", "is_stop": true, "is_punct": false, "is_negated": false, "idx": 0, "doc_idx": 0},
    {"text": "do", "lemma": "do", "pos": "AUX", "is_stop": true, "is_punct": false, "is_negated": true, "idx": 2, "doc_idx": 1},
    {"text": "n't", "lemma": "not", "pos": "PART", "is_stop": true, "is_punct": false, "is_negated": true, "idx": 4, "doc_idx": 2},
    {"text": "like", "lemma": "like", "pos": "VERB", "is_stop": false, "is_punct": false, "is_negated": true, "idx": 8, "doc_idx": 3},
    ...
  ],
  "token_count": 5,
  "negated_count": 3,
  "negation_markers": ["n't"]
}
```

Note: spaCy splits contractions (e.g., "don't" → ["do", "n't"]). The "n't" token has lemma "not", which is matched as a negation marker.

## Implementation Notes

### Negation Marker List (v1)
```python
NEGATION_MARKERS = {
    "not", "no", "never", "neither", "nor",
    # Note: contractions like "don't", "can't", etc. are split by spaCy into
    # base form + "n't" (e.g., "don't" → ["do", "n't"]).
    # The "n't" token has lemma "not", which is matched below.
    # So we only need "not" in the marker list; contraction detection works via lemma.
}
# Matching strategy: check both token.text.lower() and token.lemma_.lower()
# against this set. For contractions, the lemma "not" will match.
```

### Detection Algorithm
1. Tokenize input text using spaCy (or import from tokenizer module)
2. For each token, check if it's a negation marker (lemma or text, case-insensitive)
3. If negation found, mark all tokens within `window` distance (before and after) as negated
4. Build enriched Token objects with `is_negated=True/False`
5. Return list

```python
import spacy
from tools.tokenizer import Token

def detect_negations(text: str, window: int = 5) -> List[Token]:
    if text is None or not isinstance(text, str):
        raise ValueError("Text must be a string")
    if not isinstance(window, int) or window < 1:
        raise ValueError("Window must be a positive integer")
    
    # Tokenize
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    
    # Find negation marker positions
    negation_positions = set()
    for doc_idx, spacy_token in enumerate(doc):
        if spacy_token.lemma_.lower() in NEGATION_MARKERS or spacy_token.text.lower() in NEGATION_MARKERS:
            negation_positions.add(doc_idx)
    
    # Mark tokens within window of negations
    negated_indices = set()
    for neg_pos in negation_positions:
        for i in range(max(0, neg_pos - window), min(len(doc), neg_pos + window + 1)):
            negated_indices.add(i)
    
    # Build enriched tokens
    tokens = []
    for doc_idx, spacy_token in enumerate(doc):
        token = Token(
            text=spacy_token.text,
            lemma=spacy_token.lemma_,
            pos=spacy_token.pos_,
            is_stop=spacy_token.is_stop,
            is_punct=spacy_token.is_punct,
            is_space=spacy_token.is_space,
            idx=spacy_token.idx,
            doc_idx=doc_idx,
            is_negated=(doc_idx in negated_indices)
        )
        tokens.append(token)
    
    return tokens
```

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("negation_detector")

logger.log(event_type="negation_detection_started", data={"source": input_path, "window": window})
logger.log(event_type="negation_detection_complete", data={
    "source": input_path,
    "token_count": len(tokens),
    "negated_count": sum(1 for t in tokens if t.is_negated),
    "negation_markers_found": list(negation_positions)
})
logger.error(event_type="negation_detection_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Happy path:** "I don't like this" → mark "don't", "like", etc. as negated within window
2. **Multiple negations:** "I don't like and won't accept" → detect both markers, mark affected tokens
3. **No negation:** "I like this" → all is_negated=False
4. **Negation marker at start:** "Never do that" → mark "Never", "do", "that" as negated
5. **Window boundary:** "I don't like" with window=2 → mark "don't", "like"; not "I"
6. **Custom window:** Same text with window=1 → mark only "don't" and immediate neighbors
7. **Contractions:** "Can't help it" → detect "Can't" as negation marker
8. **Already-negated text:** "It's not impossible" (double negative) → mark "not" and "impossible" as negated (v2+ can handle logical negation)
9. **Empty input:** Empty string → empty token list (not an error)
10. **None input:** Pass None → verify `ValueError`
11. **Invalid window:** window=0 or window=-1 → verify `ValueError`
12. **Case insensitivity:** "NOT GOOD" → detect "NOT" as negation marker

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works for reading/writing with custom window size
- Negation markers detected correctly (hardcoded list)
- Tokens within window marked as negated
- Tokens outside window not marked as negated
- Multiple negations handled correctly
- Error cases raise appropriate exceptions
- JSON output is valid and complete (includes is_negated field)
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/negation_detector/
  __init__.py            # exports detect_negations()
  core.py                # detect_negations() implementation
  cli.py                 # argparse CLI
  token_schema.py        # reuse Token from tokenizer (or import)
  negation_markers.py    # NEGATION_MARKERS constant + helpers
  README.md              # usage docs
```

## Dependencies
- `spacy` (reuse from tokenizer; already installed)
- `en_core_web_sm` (reuse from tokenizer)

## Integration Points
- Reuses `Token` dataclass from tokenizer (add `is_negated` field)
- Takes raw text or pre-tokenized tokens (if later), outputs enriched tokens
- Can chain with tokenizer output or run standalone

## Future Extensions (v2+)
- Linguistic scope analysis (determine what negation applies to)
- Multi-word negations ("in no way", "not at all")
- Negation of negation (double negatives, logical evaluation)
- Intensifiers (e.g., "very not", "absolutely not")
- Domain-specific negation patterns (medical, legal, scientific)
- Integration with dependency parsing (use parse tree to determine scope)
- Confidence scores (how sure we are a token is negated)

## Done When
- `tools/negation_detector/__init__.py` exports `detect_negations()`
- `tools/negation_detector/core.py` implements core logic
- `tools/negation_detector/cli.py` implements CLI via argparse
- `tools/negation_detector/negation_markers.py` defines marker list
- `tools/negation_detector/README.md` documents API and usage
- All 12 manual test cases pass with pasted output
- JSON output includes `is_negated` field on each token
- `tools/README.md` updated to list negation_detector
