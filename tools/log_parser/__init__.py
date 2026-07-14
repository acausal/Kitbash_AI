"""tools.log_parser package.

Library (functions return JSON-serializable dicts):
    from tools.log_parser import (
        parse_jsonl_traces, parse_json_trace, normalize_trace,
        filter_traces, aggregate_chains, extract_chain_steps,
    )
"""
from .core import (
    aggregate_chains,
    extract_chain_steps,
    filter_traces,
    normalize_trace,
    parse_json_trace,
    parse_jsonl_traces,
)
from .log_schema import (
    AggregatedChainStats,
    ChainStep,
    FilterReport,
    ParseReport,
    Trace,
    TransitionStats,
)

__all__ = [
    "parse_jsonl_traces", "parse_json_trace", "normalize_trace",
    "filter_traces", "aggregate_chains", "extract_chain_steps",
    "ChainStep", "Trace", "ParseReport", "FilterReport",
    "AggregatedChainStats", "TransitionStats",
]
