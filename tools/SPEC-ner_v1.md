# SPEC: Named Entity Recognition (NER) v1

## Purpose
Extract named entities (people, organizations, locations, dates, etc.) from text. Uses spaCy's pre-trained NER model to identify entity spans and their types. Designed as a standalone input-sieve component; entities are extracted without linguistic scope analysis or relationship inference (those are v2+ features).

## Scope

### In Scope
- Accept raw text input
- Extract entities using spaCy's NER model (en_core_web_sm)
- Return entity spans (text, label, character positions)
- Supported entity types (spaCy default): PERSON, ORG, GPE, DATE, TIME, MONEY, QUANTITY, ORDINAL, CARDINAL, EVENT, FAC, LANGUAGE, LAW, NORP, PERCENT, PRODUCT, WORK_OF_ART
- CLI entry point: `python -m tools.ner <input.txt> [--labels PERSON,ORG] [--output output.json]`
- Library API: `extract_entities(text: str, labels: List[str] | None = None) -> List[Entity]`
- Structured logging via `structured_logger.py`

### Non-Goals (v1)
- Fine-tuning NER model on custom data
- Custom entity types (use spaCy's defaults)
- Entity linking (linking entities to knowledge bases)
- Relationship extraction (who did what to whom)
- Domain-specific NER (medical, legal, scientific)
- Confidence scoring (spaCy provides no per-entity confidence)

## Data Structures

### Entity (dataclass)
```python
from dataclasses import dataclass

@dataclass
class Entity:
    text: str              # Entity text as it appears in document
    label: str             # Entity type (PERSON, ORG, GPE, DATE, etc.)
    start: int             # Character offset (start)
    end: int               # Character offset (end, exclusive)
    doc_idx: int           # Index in entity sequence (for ordering)
```

## API Contract

### Library API
```python
from tools.ner import extract_entities, Entity

entities = extract_entities("Apple CEO Tim Cook announced a new product.")
# Returns: [Entity(text="Apple", label="ORG", start=0, end=5, ...), ...]

entities = extract_entities("...", labels=["PERSON", "ORG"])
# Filter to only PERSON and ORG entities
```

**Signature:**
```python
def extract_entities(text: str, labels: List[str] | None = None) -> List[Entity]:
    """
    Extract named entities from text using spaCy NER.
    
    Args:
        text: Raw input text
        labels: Optional list of entity labels to filter by (e.g., ["PERSON", "ORG"]).
                If None, return all entities.
    
    Returns:
        List of Entity objects sorted by appearance order
    
    Raises:
        ValueError: Text is None or not a string
        ValueError: Labels contains unrecognized entity type
    """
```

### CLI
```bash
python -m tools.ner input.txt
python -m tools.ner input.txt --labels PERSON,ORG
python -m tools.ner input.txt -l PERSON,ORG,GPE
python -m tools.ner input.txt --output entities.json
```

**Behavior:**
- Read input text from file
- Extract entities (optionally filter by label)
- Write JSON output (default: stdout)
- Exit code 0 on success, 1 on failure
- Print summary to stdout: `Extracted <N> entities from <input> (<K> PERSON, <M> ORG, ...)`

**Output format (JSON):**
```json
{
  "entities": [
    {"text": "Apple", "label": "ORG", "start": 0, "end": 5, "doc_idx": 0},
    {"text": "Tim Cook", "label": "PERSON", "start": 10, "end": 18, "doc_idx": 1},
    {"text": "new product", "label": "PRODUCT", "start": 35, "end": 47, "doc_idx": 2}
  ],
  "entity_count": 3,
  "label_counts": {
    "ORG": 1,
    "PERSON": 1,
    "PRODUCT": 1
  }
}
```

## Implementation Notes

### spaCy NER Integration
- Load model: `nlp = spacy.load("en_core_web_sm")`
- Process text: `doc = nlp(text)`
- Iterate over `doc.ents`: extract text, label, start/end character positions
- Build Entity objects

```python
import spacy
from tools.ner import Entity

def extract_entities(text: str, labels: List[str] | None = None) -> List[Entity]:
    if text is None or not isinstance(text, str):
        raise ValueError("Text must be a string")
    
    # Validate labels if provided
    VALID_LABELS = {
        "PERSON", "ORG", "GPE", "DATE", "TIME", "MONEY", "QUANTITY",
        "ORDINAL", "CARDINAL", "EVENT", "FAC", "LANGUAGE", "LAW", "NORP",
        "PERCENT", "PRODUCT", "WORK_OF_ART"
    }
    if labels:
        invalid = set(labels) - VALID_LABELS
        if invalid:
            raise ValueError(f"Unrecognized entity labels: {invalid}. Valid: {sorted(VALID_LABELS)}")
    
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise RuntimeError("spaCy model 'en_core_web_sm' not installed. Run: python -m spacy download en_core_web_sm")
    
    doc = nlp(text)
    entities = []
    
    for doc_idx, ent in enumerate(doc.ents):
        # Filter by label if specified
        if labels and ent.label_ not in labels:
            continue
        
        entity = Entity(
            text=ent.text,
            label=ent.label_,
            start=ent.start_char,
            end=ent.end_char,
            doc_idx=doc_idx
        )
        entities.append(entity)
    
    return entities
```

### Logging
```python
from structured_logger import get_event_logger
logger = get_event_logger("ner")

logger.log(event_type="ner_extraction_started", data={"source": input_path, "labels_filter": labels})
label_counts = {}
for entity in entities:
    label_counts[entity.label] = label_counts.get(entity.label, 0) + 1

logger.log(event_type="ner_extraction_complete", data={
    "source": input_path,
    "entity_count": len(entities),
    "label_counts": label_counts
})
logger.error(event_type="ner_extraction_failed", data={"source": input_path, "error": str(e)})
```

## Testing & Validation

### Manual Test Cases
1. **Happy path:** "Apple CEO Tim Cook..." → extract Apple (ORG), Tim Cook (PERSON)
2. **Multiple entity types:** "Microsoft in Seattle..." → extract Microsoft (ORG), Seattle (GPE)
3. **Dates/times:** "Meeting on January 15, 2024 at 3 PM" → extract entities with DATE and TIME labels
4. **Money/quantities:** "Revenue of $1.2 billion..." → extract MONEY entities
5. **Filter by label:** Same text with `--labels PERSON,ORG` → exclude dates/times
6. **No entities:** "This is a simple sentence." → empty entity list (not an error)
7. **Empty input:** Empty string → empty entity list (not an error)
8. **Overlapping entities:** "New York City" → single GPE entity (not split)
9. **None input:** Pass None → verify `ValueError`
10. **Invalid label filter:** `labels=["FAKE"]` → verify `ValueError` with helpful message
11. **Case insensitivity in output:** Entity text preserves original case
12. **Character offsets:** Verify start/end positions match actual text boundaries

### Acceptance Criteria
- Library function imports and calls cleanly
- CLI works for reading/writing with optional label filtering
- Entities extracted correctly (text, label, positions)
- Character offsets (start/end) are accurate
- Label filtering works (include only specified types)
- Multiple entity types handled correctly
- Error cases raise appropriate exceptions
- JSON output is valid and complete (includes label_counts)
- Pasted terminal output demonstrating all test cases

## Module Structure
```
tools/ner/
  __init__.py            # exports extract_entities()
  core.py                # extract_entities() implementation
  cli.py                 # argparse CLI
  entity_schema.py       # Entity dataclass definition
  README.md              # usage docs
```

## Dependencies
- `spacy` (reuse from tokenizer; already installed)
- `en_core_web_sm` (reuse from tokenizer)

## spaCy Entity Types (v1 Reference)
- **PERSON:** People, including fictional
- **ORG:** Companies, agencies, institutions, etc.
- **GPE:** Geopolitical entities (countries, cities, states)
- **DATE:** Absolute or relative dates
- **TIME:** Times smaller than a day
- **MONEY:** Monetary values, including units
- **QUANTITY:** Measurements, as of weight or distance
- **ORDINAL:** "first", "second", etc.
- **CARDINAL:** Numerals that do not fall under another type
- **EVENT:** Named hurricanes, battles, wars, sports events, etc.
- **FAC:** Buildings, airports, highways, bridges, etc.
- **LANGUAGE:** Any named language
- **LAW:** Named documents made into laws
- **NORP:** Nationalities or religious or political groups
- **PERCENT:** Percentage (including "%")
- **PRODUCT:** Objects, vehicles, foods, etc. (not services)
- **WORK_OF_ART:** Titles of books, songs, etc.

## Future Extensions (v2+)
- Fine-tuned NER model for domain-specific entity types (medical, legal, scientific)
- Custom entity recognition via rule-based patterns
- Entity linking (linking entities to knowledge bases, disambiguating)
- Confidence scores for each entity
- Multi-language support (load language-specific models)
- Relationship extraction (connections between entities)
- Entity normalization (canonical forms, aliases)

## Done When
- `tools/ner/__init__.py` exports `extract_entities()` and `Entity`
- `tools/ner/core.py` implements extraction logic
- `tools/ner/cli.py` implements CLI via argparse
- `tools/ner/entity_schema.py` defines Entity dataclass
- `tools/ner/README.md` documents API and usage
- All 12 manual test cases pass with pasted output
- JSON output includes `label_counts` summary
- Label filtering works correctly
- `tools/README.md` updated to list ner
