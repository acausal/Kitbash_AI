"""ner core: named-entity extraction via spaCy (input-sieve component).

Isolation-first tool (see tools/README.md). Allowed imports: stdlib, spaCy,
and Kitbash core's structured_logger (read-only helper). No orchestrator/
engine/redis imports.

v1: spaCy en_core_web_sm default entity types, optional label filtering. No
fine-tuning, entity linking, relationships, or confidence scores (v2+).
"""
from __future__ import annotations

from typing import List, Optional

from .entity_schema import Entity

try:
    from structured_logger import get_event_logger
    _logger = get_event_logger("ner")
except Exception:  # structured_logger optional; never let logging break the tool
    _logger = None

# spaCy en_core_web_sm default entity types.
VALID_LABELS = frozenset({
    "PERSON", "ORG", "GPE", "DATE", "TIME", "MONEY", "QUANTITY",
    "ORDINAL", "CARDINAL", "EVENT", "FAC", "LANGUAGE", "LAW", "NORP",
    "PERCENT", "PRODUCT", "WORK_OF_ART",
})

_NLP_CACHE: dict = {}


def _load_model(model: str = "en_core_web_sm"):
    if model in _NLP_CACHE:
        return _NLP_CACHE[model]
    try:
        import spacy
    except ImportError as e:
        raise RuntimeError("spaCy not installed. Run: pip install spacy") from e
    try:
        nlp = spacy.load(model)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model}' not installed. "
            f"Run: python -m spacy download {model}"
        ) from e
    _NLP_CACHE[model] = nlp
    return nlp


def extract_entities(text: str, labels: Optional[List[str]] = None) -> List[Entity]:
    """Extract named entities from text using spaCy NER.

    Args:
        text: Raw input text. Empty string is allowed (returns []); None is not.
        labels: Optional list of entity labels to keep (e.g. ["PERSON", "ORG"]).
            If None, all entities are returned.

    Returns:
        List of Entity objects in order of appearance. When `labels` filters the
        output, each Entity keeps its original document entity index in doc_idx
        (indices may be non-contiguous), per SPEC.

    Raises:
        ValueError: text is None/not a string, or labels contains an unknown type.
        RuntimeError: spaCy or the model is not installed / fails to load.
    """
    if text is None or not isinstance(text, str):
        raise ValueError(
            "text must be a string (got "
            f"{'None' if text is None else type(text).__name__})"
        )
    if labels:
        invalid = set(labels) - VALID_LABELS
        if invalid:
            raise ValueError(
                f"Unrecognized entity labels: {sorted(invalid)}. "
                f"Valid: {sorted(VALID_LABELS)}"
            )

    nlp = _load_model()
    if _logger:
        _logger.log(event_type="ner_extraction_started",
                    data={"char_count": len(text), "labels_filter": labels})

    doc = nlp(text)
    label_set = set(labels) if labels else None
    entities = [
        Entity(text=ent.text, label=ent.label_,
               start=ent.start_char, end=ent.end_char, doc_idx=doc_idx)
        for doc_idx, ent in enumerate(doc.ents)
        if label_set is None or ent.label_ in label_set
    ]

    if _logger:
        counts: dict = {}
        for e in entities:
            counts[e.label] = counts.get(e.label, 0) + 1
        _logger.log(event_type="ner_extraction_complete",
                    data={"entity_count": len(entities), "label_counts": counts})
    return entities
