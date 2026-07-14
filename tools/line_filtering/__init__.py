"""tools.line_filtering package.

Library (functions return JSON-serializable dicts):
    from tools.line_filtering import (
        sort_lines, deduplicate_lines, count_line_frequency, filter_by_frequency,
        unique_lines, head_tail_lines, reverse_lines,
    )
"""
from .core import (
    count_line_frequency,
    deduplicate_lines,
    filter_by_frequency,
    head_tail_lines,
    reverse_lines,
    sort_lines,
    unique_lines,
)
from .filter_schema import (
    DistributionStats,
    DeduplicateResult,
    FilterByFrequencyResult,
    FrequencyEntry,
    FrequencyResult,
    HeadTailResult,
    SortResult,
    UniqueResult,
)

__all__ = [
    "sort_lines", "deduplicate_lines", "count_line_frequency",
    "filter_by_frequency", "unique_lines", "head_tail_lines", "reverse_lines",
    "FrequencyEntry", "DistributionStats", "SortResult", "DeduplicateResult",
    "FrequencyResult", "FilterByFrequencyResult", "UniqueResult", "HeadTailResult",
]
