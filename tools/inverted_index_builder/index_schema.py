"""Dataclasses for tools.inverted_index_builder (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Posting:
    doc_id: str
    term_frequency: int


@dataclass
class IndexEntry:
    token: str
    document_frequency: int
    idf: float
    postings: List[Posting] = field(default_factory=list)
