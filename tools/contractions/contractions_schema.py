"""Dataclasses for tools.contractions (see SPEC-contractions_v1.md).

Mirror the JSON shapes. Core functions build plain dicts (composability); these
document the contract. `position` is the 1-based word index of each contraction
in the tokenized original text (see SPEC schema note).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ContractionInstance:
    contraction: str
    expansion: str
    position: int  # 1-based word position in the original text

    def to_dict(self) -> Dict[str, Any]:
        return {"contraction": self.contraction,
                "expansion": self.expansion,
                "position": self.position}


@dataclass
class ExpandResult:
    operation: str
    preserve_case: bool
    original_text: str
    expanded_text: str
    contractions_found: int
    contractions_list: List[ContractionInstance]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "preserve_case": self.preserve_case,
            "original_text": self.original_text,
            "expanded_text": self.expanded_text,
            "contractions_found": self.contractions_found,
            "contractions_list": [c.to_dict() for c in self.contractions_list],
        }


@dataclass
class ExpandWordResult:
    operation: str
    word: str
    is_contraction: bool
    expanded: str
    case_preserved: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "word": self.word,
            "is_contraction": self.is_contraction,
            "expanded": self.expanded,
            "case_preserved": self.case_preserved,
        }


@dataclass
class ContractionDict:
    operation: str
    total_contractions: int
    contractions: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "total_contractions": self.total_contractions,
            "contractions": self.contractions,
        }
