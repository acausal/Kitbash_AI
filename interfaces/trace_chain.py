"""interfaces/trace_chain.py — CANONICAL trace chain contract (SPEC_TRACE_CHAIN_CONTRACT).

Single source of truth for the on-disk `chain` field of a dream-bucket trace
record. Both the writer (LearningObserver._log_trace) and the reader
(sleep_procedural_edge_extractor) import this so the shape can never drift.

Chain shape: a per-query SUMMARY dict (NOT a list of steps). `fact_ids` is the
only fact reference and its ORDER IS NONDETERMINISTIC (set-sourced) — never
rely on it. Edges are pairwise co-occurrence over set(fact_ids) with canonical
key a<b. Cross-query/session edges are OUT OF SCOPE (deferred ticket).
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Tuple


@dataclass
class TraceChain:
    query_id: str
    chain_type: str = "intra_query"   # "intra_query" today; "cross_query" reserved
    fact_ids: List[int] = field(default_factory=list)  # order NONDETERMINISTIC — never rely on it
    grain_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0           # raw MTR signal; NOT clamped here

    def to_dict(self) -> Dict[str, Any]:
        """Exact on-disk shape (keys must match what the diagnostic reads)."""
        d = asdict(self)
        # keep fact_ids as a list on disk (order irrelevant; consumers use set())
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TraceChain":
        """Tolerant parse; raises on missing query_id / fact_ids."""
        if not isinstance(d, dict):
            raise TypeError(f"TraceChain.from_dict expects dict, got {type(d).__name__}")
        if "query_id" not in d:
            raise ValueError("TraceChain missing required field 'query_id'")
        if "fact_ids" not in d:
            raise ValueError("TraceChain missing required field 'fact_ids'")
        return cls(
            query_id=str(d["query_id"]),
            chain_type=str(d.get("chain_type", "intra_query")),
            fact_ids=[int(x) for x in d.get("fact_ids", [])],
            grain_ids=[str(x) for x in d.get("grain_ids", [])],
            confidence=float(d.get("confidence", 0.0)),
        )


def iter_cooccurrence_edges(chain: TraceChain, cartridge: str):
    """Yield (source_fact, target_fact) for every unordered pair a<b in set(fact_ids).

    ORDER-INDEPENDENT by construction (set + a<b canonical key). Never consecutive
    pairs. Yields nothing for <2 distinct facts (thin corpus -> 0 edges, correct).
    """
    facts = sorted(set(chain.fact_ids))
    n = len(facts)
    for i in range(n):
        for j in range(i + 1, n):
            yield (facts[i], facts[j])
