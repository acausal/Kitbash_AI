"""Dataclasses for tools.tfidf_ranker (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TfidfDoc:
    doc_id: str
    tfidf: Dict[str, float]
