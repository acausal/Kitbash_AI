"""Schema for tools.relevance_gate (deterministic query-time relevance filter).

Dataclasses only — no logic, no imports beyond stdlib. Mirrors the project
convention (see tools/*/schema.py). The Relevance Gate decides which retrieved
candidate facts survive into the generation LLM's prompt; it is NOT MTR's
salience gate, NOT an InferenceEngine, NOT a relevance model. See
docs/SPEC-relevance_gate_v1.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Numeric mapping for cosine_similarity.interpret() labels. The real tool
# returns "high_similarity"/"medium_similarity"/"low_similarity" (NOT the bare
# high/medium/low the spec's mapping table sketches) — map the real labels.
SIMILARITY_BUCKET_NUMERIC = {
    "high_similarity": 1.0,
    "medium_similarity": 0.5,
    "low_similarity": 0.0,
}


@dataclass
class CandidateFact:
    """A retrieved candidate fact handed to the gate."""
    id: str
    text: str


@dataclass
class DimensionScores:
    """Per-candidate relevance dimension scores (each in [0, 1])."""
    lexical: float = 0.0
    similarity_bucket: float = 0.0
    entity_overlap: float = 0.0
    structural_overlap: float = 0.0


@dataclass
class ScoredCandidate:
    """A candidate after scoring."""
    id: str
    relevance_strength: float
    dims: DimensionScores = field(default_factory=DimensionScores)
    negation_flag: bool = False


@dataclass
class GateResult:
    """Output of apply_relevance_gate."""
    gate_fired: bool
    trigger: Optional[str]  # "margin" | "volume" | None
    selected: List[str] = field(default_factory=list)
    all_scored: List[ScoredCandidate] = field(default_factory=list)
    negation_flags: List[str] = field(default_factory=list)
    note: str = ""
