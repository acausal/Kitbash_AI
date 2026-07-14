"""tools.sequence_pattern_miner package.

Library (functions return JSON-serializable dicts):
    from tools.sequence_pattern_miner import (
        extract_ngrams, extract_ngrams_by_length, filter_sequences,
        rank_sequences_by_element_type, sequences_to_markov_transitions,
    )
"""
from .core import (
    extract_ngrams,
    extract_ngrams_by_length,
    filter_sequences,
    rank_sequences_by_element_type,
    sequences_to_markov_transitions,
)
from .sequence_schema import (
    ExtractionReport,
    ExtractionStats,
    MarkovReport,
    MarkovState,
    MarkovTransition,
    Sequence,
)

__all__ = [
    "extract_ngrams", "extract_ngrams_by_length", "filter_sequences",
    "rank_sequences_by_element_type", "sequences_to_markov_transitions",
    "Sequence", "ExtractionStats", "ExtractionReport",
    "MarkovTransition", "MarkovState", "MarkovReport",
]
