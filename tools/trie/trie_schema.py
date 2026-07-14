"""Dataclasses mirroring tools.trie JSON output (documentation)."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TrieNode:
    children: Dict[str, "TrieNode"] = field(default_factory=dict)
    terminal: bool = False


@dataclass
class SearchResult:
    query: str
    found: bool
    is_terminal: bool
    path_traversed: str


@dataclass
class PrefixResult:
    prefix: str
    matches: List[str]
    match_count: int
    truncated: bool


@dataclass
class Suggestion:
    rank: int
    completion: str
    suffix: str
    confidence: float


@dataclass
class NegationResult:
    excluded_terms: List[str]
    included_terms: List[str]
    excluded_count: int
    included_count: int
    exclusion_rate: float
