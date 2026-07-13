"""Entity dataclass for tools.ner (see SPEC-ner_v1.md)."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Entity:
    text: str        # Entity text as it appears in the document
    label: str       # Entity type (PERSON, ORG, GPE, DATE, ...)
    start: int       # Character offset (start)
    end: int         # Character offset (end, exclusive)
    doc_idx: int     # Index in the entity sequence (for ordering)

    def to_dict(self) -> dict:
        return asdict(self)
