"""ParseResult dataclass for tools.structured_validator (see SPEC-structured_validator_v1.md)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class ParseResult:
    success: bool                     # True if parse succeeded
    parse_tree: Optional[Any]         # Serialized tree (dict) if success, else None
    error: Optional[str]              # Error message if success is False
    grammar_name: str                 # Which grammar was used ("inline" or file name)
    input_text: str                   # Original input

    def to_dict(self) -> dict:
        return asdict(self)
