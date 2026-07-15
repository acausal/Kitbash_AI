"""Dataclasses for tools.boolean_search (see SPEC)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class QueryNode:
    op: str  # 'AND' | 'OR' | 'NOT' | 'TERM'
    left: Optional["QueryNode"] = None
    right: Optional["QueryNode"] = None
    term: Optional[str] = None
