"""tools.text_search package.

Library (functions return JSON-serializable dicts):
    from tools.text_search import (
        search_text, search_lines, search_and_extract,
        count_matches, replace_matches,
    )
"""
from .core import (
    count_matches,
    replace_matches,
    search_and_extract,
    search_lines,
    search_text,
)
from .search_schema import (
    ContextLine,
    CountReport,
    ExtractedGroup,
    Match,
    MatchPosition,
    ReplaceChange,
    ReplaceReport,
    SearchReport,
    SearchResults,
)

__all__ = [
    "search_text", "search_lines", "search_and_extract",
    "count_matches", "replace_matches",
    "ContextLine", "MatchPosition", "Match", "SearchResults", "SearchReport",
    "ExtractedGroup", "CountReport", "ReplaceChange", "ReplaceReport",
]
