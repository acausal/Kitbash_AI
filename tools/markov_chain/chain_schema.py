"""Dataclasses for tools.markov_chain (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Transition:
    context: Tuple[str, ...]
    next_token: str
    count: int
    probability: float
