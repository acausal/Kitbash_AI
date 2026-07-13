# SPEC: Tokenizer v1

## Purpose
Generic text tokenization for use in input sieve (user queries) and document preprocessing (extracted text). Produces clean token sequences from raw text using spaCy. Designed to be language-agnostic and extensible; v2+ will add slang/abbreviation/variation normalization.

## Scope

### In Scope
- Accept raw text input (any source: user query, extracted document text, etc.)
- Tokenize using spaCy (whitespace + punctuation-aware)
- Optionally lemmatize tokens (base form)
- Optionally filter stop words
- Return list of Token objects (text, lemma, POS, is_stop, etc.)
- CLI entry point: `python -m tools.tokenizer <input.txt> [--lemma] [--remove-stop]`
- Library API: `tokenize(text: str, lemmatize: bool = False, remove_stop: bool = False) -> List[Token]`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Slang normalization (e.g., "gonna" → "going to")
- Abbreviation expansion (e.g., "Mr." → "Mister")
- Spelling correction
- Domain-specific tokenization (use domain specializers in v2+)
- Multi-language support (assume English; v2+ decision point)
- Entity extraction (that's NER's job)

## Data Structures

### Token (dataclass)
```python
from dataclasses import dataclass

@dataclass
class Token:
    text: str              # Original token text
    lemma: str             # Base form (if lemmatized)
    pos: str               # Part of speech (NOUN, VERB, ADJ, etc.)
    is_stop: bool          # Is this a stop word?
    is_punct: bool         # Is this punctuation?
    is_space: bool         # Is this whitespace?
    idx: int               # Character offset in original text
    doc_idx: int           # Index in token sequence
```

## API Contract

### Library API
```python
from tools.tokenizer import tokenize, Token

tokens = tokenize("What is machine learning?")
# Returns: [Token(text="What", lemma="what", pos="AUX", is_stop=True, ...), ...]

tokens = tokenize("What is machine learning?", lemmatize=True, remove_stop=False)
# Includes lemmas, keeps stop words

tokens = tokenize("What is machine learning?", lemmatize=True, remove_stop=True)
# Excludes stop words
```

**Signature:**
```python
def tokenize(
    text: str,
    lemmatize: bool = False,
    remove_stop: bool = False,
    model: str = "en_core_web_sm"
) -> List[Token]:
    """
    Tokenize text using spaCy.
    
    Args:
        text: Raw input text (empty string is allowed, None is not)
        lemmatize: If True, include lemma field for each token
        remove_stop: If True, exclude stop words from output
        model: spaCy model to use (default: en_core_web_sm)
    
    Returns:
        List of Token objects (empty list if text is empty)
    
    Raises:
        ValueError: Text is None or not a string
        RuntimeError: spaCy model not installed or fails to load
    """
```

### CLI
```bash
python -m tools.tokenizer input.txt
python -m tools.tokenizer input.txt --lemma --remove-stop
python -m tools.tokenizer input.txt -l -s
```

**Behavior:**
- Read input text from file
- Tokenize with spaCy (default model: en_core_web_sm)
- Output format: JSON array of Token objects (one per line or compact)
- Exit code 0 on success, 1 on failure
- Print summary to stdout: `Tokenized <input> → <N> tokens (<K> stop words removed if --remove-stop)`

**Output format (JSON):**
```json
{
  "tokens": [
    {"text": "What", "lemma": "what", "pos": "AUX", "is_stop": true, "is_punct": false, "idx": 0, "doc_idx": 0},
    {"text": "is", "lemma": "be", "pos": "AUX", "is_stop": true, "is_punct": false, "idx": 5, "doc_idx": 1},
    ...
  ],
  "token_count": 5,
  "stop_word_count": 2
}
```

## Implementation Notes

### spaCy Integration
- Load model: `nlp = spacy.load("en_core_web_sm")`
- Process text: `doc = nlp(text)`
- Iterate over doc.tokens: extract text, lemma, pos_, is_stop
- Build Token objects

```python
import spacy
from tools.tokenizer import Token

def tokenize(text: str, lemmatize: bool = False, remove_stop: bool = False, model: str = "en_core_web_sm") -> List[Token]:
    if text is None or not isinstance(text, str):
        raise ValueError("Text must be a string")
    
    try:
        nlp = spacy.load(model)
    except OSError:
        raise RuntimeError(f"spaCy model '{model}' not installed. Run: python -m spacy download {model}")
    
    doc = nlp(text)
    tokens = []
    
    for doc_idx, spacy_token in enumerate(doc):
        if remove_stop and spacy_token.is_stop:
            continue
        
        token = Token(
            text=spacy_token.text,
            lemma=spacy_token.lemma_ if lemmatize else spacy_token.text,
            pos=spacy_token.pos_,
            is_stop=spacy_token.is_stop,
            is_punct=spacy_token.is_punct,
            is_space=spacy_token.is_space,
            idx=spacy_token.idx,
            doc_idx=doc_idx
        )
        tokens.append(token)
    
    return tokens
```

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("tokenizer")

logger.log(event_type="tokenization_started", data={"source": input_path, "char_count": len(text)})
logger.log(event_type="tokenization_complete", data={
    "source": input_path,
    "token_count": len(tokens),
    "stop_word_count": sum(1 for t in tokens if t.is_stop),
    "punct_count": sum(1 for t in tokens if t.is_punct)
})
logger.error(event_type="tokenization_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Happy path:** Simple sentence → verify tokens extracted correctly (text, lemma, POS)
2. **Lemmatization:** "running" + `--lemma` → lemma="run"
3. **Stop word removal:** "What is X?" + `--remove-stop` → excludes "What", "is"
4. **Punctuation:** "Hello, world!" → separate tokens for "," and "!"
5. **Numbers:** "123 abc" → tokenize numbers correctly
6. **Contractions:** "don't" → single token or two (spaCy default)
7. **Empty input:** Empty string → empty token list (not an error)
8. **None input:** Pass None → verify `ValueError`
9. **Non-string input:** Pass int/list → verify `ValueError`
10. **Missing spaCy model:** Model not installed → verify `RuntimeError`

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works for reading/writing
- Lemmatization works correctly (with/without flag)
- Stop word removal works correctly (with/without flag)
- POS tags are accurate (spot-check a few)
- Token metadata (idx, doc_idx, is_punct, is_space, is_stop) correct
- Error cases raise appropriate exceptions
- JSON output is valid and complete
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/tokenizer/
  __init__.py          # exports tokenize(), Token
  core.py              # tokenize() implementation
  cli.py               # argparse CLI
  token_schema.py      # Token dataclass definition
  README.md            # usage docs
```

## Dependencies
- `spacy` (PyPI; pure Python, lightweight)
- `en_core_web_sm` (spaCy English model; ~40MB, can be installed separately)

## Future Extensions (v2+)
- Slang normalization ("gonna" → "going to", "ur" → "you are", etc.)
- Abbreviation expansion ("Dr." → "Doctor", "Mr." → "Mister")
- Spelling correction (typo detection + fixing)
- Domain-specific tokenizers (medical, legal, scientific via spaCy-stanza or stanza directly)
- Multi-language support (auto-detect language, load appropriate spaCy model)
- Custom stop word lists per domain
- Subword tokenization (BPE, WordPiece) for integration with LLM tokenizers

## Done When
- `tools/tokenizer/__init__.py` exports `tokenize()` and `Token`
- `tools/tokenizer/cli.py` implements CLI via argparse
- `tools/tokenizer/token_schema.py` defines Token dataclass
- `tools/tokenizer/README.md` documents API and usage
- All 10 manual test cases pass with pasted output
- JSON output format is valid and consistent
- `tools/README.md` updated to list tokenizer
