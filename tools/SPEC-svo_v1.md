# SPEC: Subject-Verb-Object (SVO) Extraction v1

## Purpose
Extract subject-verb-object triples from text using spaCy's dependency parser. Identifies the main actions and actors in sentences, complementing NER (entities) and negation detection (modifiers) for complete input understanding. v1 extracts simple main-clause SVOs; complex nested structures deferred to v2+.

## Scope

### In Scope
- Accept raw text input
- Parse dependencies using spaCy (en_core_web_sm)
- Identify main verbs (ROOT dependencies) and their subjects/objects
- Return SVO triples (subject text, verb text, object text, with char positions)
- Handle edge cases: missing object (optional), missing subject (optional), multiple SVOs per sentence
- CLI entry point: `python -m tools.svo <input.txt> [--output output.json]`
- Library API: `extract_svo(text: str) -> List[SVO]`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Nested/subordinate clauses (handle main clause only; v2+ can recurse)
- Complex verb phrases (phrasal verbs, modal+verb compounds)
- Implicit subjects ("Raining" → no subject)
- Semantic roles beyond S/V/O (who/what/where/when/why)
- Confidence scoring
- Handling of passives (simplified: treat passive object as object)

## Data Structures

### SVO (dataclass)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SVO:
    subject: Optional[str]     # Subject text (None if missing)
    verb: str                  # Verb text (required)
    obj: Optional[str]         # Object text (None if missing)
    subject_start: Optional[int]   # Char offset for subject
    subject_end: Optional[int]     # Char offset for subject
    verb_start: int            # Char offset for verb
    verb_end: int              # Char offset for verb
    obj_start: Optional[int]       # Char offset for object
    obj_end: Optional[int]         # Char offset for object
    sentence: str              # Full sentence text for context
    doc_idx: int               # Index in SVO sequence
```

## API Contract

### Library API
```python
from tools.svo import extract_svo, SVO

svos = extract_svo("The CEO announced a new product.")
# Returns: [SVO(subject="The CEO", verb="announced", obj="a new product", ...)]

svos = extract_svo("Alice likes Bob and Bob likes Charlie.")
# Returns: [SVO(...), SVO(...)] — one per main clause
```

**Signature:**
```python
def extract_svo(text: str) -> List[SVO]:
    """
    Extract subject-verb-object triples from text.
    
    Args:
        text: Raw input text
    
    Returns:
        List of SVO objects (one per main clause/verb)
    
    Raises:
        ValueError: Text is None or not a string
    """
```

### CLI
```bash
python -m tools.svo input.txt
python -m tools.svo input.txt --output triples.json
python -m tools.svo input.txt -o triples.json
```

**Behavior:**
- Read input text from file
- Extract SVOs using spaCy dependency parsing
- Write JSON output (default: stdout)
- Exit code 0 on success, 1 on failure
- Print summary to stdout: `Extracted <N> SVO triples from <input> (<K> with subjects, <M> with objects)`

**Output format (JSON):**
```json
{
  "svos": [
    {
      "subject": "The CEO",
      "verb": "announced",
      "obj": "a new product",
      "subject_start": 4,
      "subject_end": 11,
      "verb_start": 12,
      "verb_end": 20,
      "obj_start": 23,
      "obj_end": 39,
      "sentence": "The CEO announced a new product.",
      "doc_idx": 0
    }
  ],
  "svo_count": 1,
  "with_subject": 1,
  "with_object": 1
}
```

## Implementation Notes

### spaCy Dependency Parsing
- Load model: `nlp = spacy.load("en_core_web_sm")`
- Process text: `doc = nlp(text)`
- Iterate over sentences: `for sent in doc.sents`
- For each sentence, find ROOT token (the main verb)
- Walk dependency tree to find subjects and objects

```python
import spacy
from tools.svo import SVO

def extract_svo(text: str) -> List[SVO]:
    if text is None or not isinstance(text, str):
        raise ValueError("Text must be a string")
    
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise RuntimeError("spaCy model 'en_core_web_sm' not installed. Run: python -m spacy download en_core_web_sm")
    
    doc = nlp(text)
    svos = []
    doc_idx = 0
    
    for sent in doc.sents:
        # Find main verb (ROOT dependency)
        root_token = sent.root
        
        # Find subject (nsubj or nsubjpass dependency)
        subject = None
        subject_start = None
        subject_end = None
        for token in sent:
            if token.dep_ in ("nsubj", "nsubjpass") and token.head == root_token:
                subject = token.text
                subject_start = token.idx
                subject_end = token.idx + len(token.text)
                break
        
        # Find object (dobj, iobj, attr, or pobj for prepositions)
        obj = None
        obj_start = None
        obj_end = None
        for token in sent:
            if token.dep_ in ("dobj", "iobj", "attr") and token.head == root_token:
                obj = token.text
                obj_start = token.idx
                obj_end = token.idx + len(token.text)
                break
        
        # Create SVO
        svo = SVO(
            subject=subject,
            verb=root_token.text,
            obj=obj,
            subject_start=subject_start,
            subject_end=subject_end,
            verb_start=root_token.idx,
            verb_end=root_token.idx + len(root_token.text),
            obj_start=obj_start,
            obj_end=obj_end,
            sentence=sent.text,
            doc_idx=doc_idx
        )
        svos.append(svo)
        doc_idx += 1
    
    return svos
```

### Dependency Relations (spaCy)
- **nsubj:** Nominal subject (active voice)
- **nsubjpass:** Nominal subject (passive voice)
- **dobj:** Direct object
- **iobj:** Indirect object
- **attr:** Attribute (e.g., "He is a doctor" → "doctor" is attr)
- **ROOT:** Main verb of the sentence

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("svo")

logger.log(event_type="svo_extraction_started", data={"source": input_path})
logger.log(event_type="svo_extraction_complete", data={
    "source": input_path,
    "svo_count": len(svos),
    "with_subject": sum(1 for s in svos if s.subject),
    "with_object": sum(1 for s in svos if s.obj)
})
logger.error(event_type="svo_extraction_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Simple SVO:** "The CEO announced a new product." → subject="The CEO", verb="announced", obj="a new product"
2. **Missing object:** "She laughed." → subject="She", verb="laughed", obj=None
3. **Missing subject (imperative):** "Run faster!" → subject=None, verb="Run", obj=None (or obj="faster" as adverb?)
4. **Multiple SVOs:** "Alice loves Bob and Charlie hates Eve." → 2 SVOs
5. **Passive voice:** "The product was announced by the CEO." → subject="The product", verb="announced", obj=None or CEO
6. **Complex noun phrase:** "The young CEO of Apple announced..." → subject="CEO" (head word) or full phrase?
7. **Prepositional object:** "He put the book on the table." → obj="the book" (dobj), "the table" (pobj—v2+)
8. **Attribute:** "He is a doctor." → subject="He", verb="is", obj="doctor" (attr)
9. **No main verb:** "What a day!" → no ROOT → no SVO (edge case, allowed)
10. **Empty input:** Empty string → empty SVO list (not an error)
11. **None input:** Pass None → verify `ValueError`
12. **Sentence with multiple verbs:** "I think he likes her." → 1 SVO for main clause (v2+ handles subordinates)

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works for reading/writing
- Simple SVO extraction works (subject/verb/object)
- Handles missing subject/object gracefully (None fields)
- Multiple SVOs per text extracted correctly
- Character offsets (start/end) are accurate and match text
- Dependency parsing dependencies (nsubj, dobj, etc.) correctly identified
- Passive voice handled (subject is still extracted)
- Error cases raise appropriate exceptions
- JSON output is valid and complete (includes counts)
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/svo/
  __init__.py            # exports extract_svo()
  core.py                # extract_svo() implementation
  cli.py                 # argparse CLI
  svo_schema.py          # SVO dataclass definition
  README.md              # usage docs
```

## Dependencies
- `spacy` (reuse from tokenizer; already installed)
- `en_core_web_sm` (reuse from tokenizer)

## Future Extensions (v2+)
- Nested/subordinate clause handling (recurse into clauses)
- Complex verb phrases (phrasal verbs, modals)
- Semantic role labeling (SRL—who/what/where/when/why beyond S/V/O)
- Implicit subject recovery ("Raining" → infer "It is raining")
- Preposition attachment (distinguish "on the table" vs other roles)
- Confidence scores for extracted triples
- Relation to negation (mark SVOs affected by negation from negation_detector)
- Multi-language support

## Done When
- `tools/svo/__init__.py` exports `extract_svo()` and `SVO`
- `tools/svo/core.py` implements extraction logic
- `tools/svo/cli.py` implements CLI via argparse
- `tools/svo/svo_schema.py` defines SVO dataclass
- `tools/svo/README.md` documents API and usage
- All 12 manual test cases pass with pasted output
- Character offsets are verified accurate
- JSON output includes `with_subject` and `with_object` counts
- `tools/README.md` updated to list svo
