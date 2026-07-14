"""SVO dataclass for tools.svo (see SPEC-svo_v1.md)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class SVO:
    subject: Optional[str]       # Subject text (head word); None if missing
    verb: str                    # Verb text (required; sentence ROOT)
    obj: Optional[str]           # Object text (head word); None if missing
    subject_start: Optional[int] # Char offset (start) for subject
    subject_end: Optional[int]   # Char offset (end, exclusive) for subject
    verb_start: int              # Char offset (start) for verb
    verb_end: int                # Char offset (end, exclusive) for verb
    obj_start: Optional[int]     # Char offset (start) for object
    obj_end: Optional[int]       # Char offset (end, exclusive) for object
    sentence: str                # Full sentence text for context
    doc_idx: int                 # Index in the SVO sequence

    def to_dict(self) -> dict:
        return asdict(self)
