"""tools.success_pattern_miner package.

Mirror of sequence_pattern_miner but success-filtered: mine recurring tool
sequences, grain activations, and mixed co-occurrence patterns from *successful*
execution traces (outcome == "success" OR error_signal < success_threshold).

Library:
    from tools.success_pattern_miner import (
        mine_success_tool_sequences, mine_success_grain_patterns,
        mine_mixed_success_patterns, ngrams, filter_success_traces,
    )
    result = mine_success_tool_sequences(traces, min_frequency=3,
                                          success_threshold=0.2)
    # result: {"patterns":[...], "success_traces_count":N, ...}

CLI:
    python -m tools.success_pattern_miner --input traces.jsonl \
        --pattern-type sequences --min-frequency 3 --output patterns.json

Pure stdlib. See SPEC-success_pattern_miner_v1.md.
"""
from .core import (
    mine_success_tool_sequences,
    mine_success_grain_patterns,
    mine_mixed_success_patterns,
)
from .pattern_extraction import ngrams
from .filtering import filter_success_traces, is_success
from .miner_schema import Pattern, RunResult

__all__ = [
    "mine_success_tool_sequences", "mine_success_grain_patterns",
    "mine_mixed_success_patterns", "ngrams", "filter_success_traces",
    "is_success", "Pattern", "RunResult",
]
