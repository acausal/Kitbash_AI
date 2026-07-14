"""Negation (exclude-by-prefix) handling for tools.trie (stdlib only)."""
from typing import Dict, List, Optional

from .core import _all_words, _norm


def negation_search(trie: dict, patterns: List[str], case_sensitive: bool = True,
                     max_results: Optional[int] = None) -> dict:
    """Return all vocabulary terms NOT starting with any exclusion prefix."""
    if not isinstance(patterns, list) or len(patterns) == 0:
        raise ValueError("patterns must be a non-empty list")
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    for p in patterns:
        if not isinstance(p, str) or p == "":
            raise ValueError(f"invalid negation pattern: {p!r}")
    all_terms = _all_words(trie)
    norm_patterns = [_norm(p, case_sensitive) for p in patterns]
    excluded = [t for t in all_terms
                if any(_norm(t, case_sensitive).startswith(p) for p in norm_patterns)]
    included = [t for t in all_terms if t not in excluded]
    if max_results is not None:
        included = included[:max_results]
    return {
        "negation_patterns": patterns,
        "case_sensitive": case_sensitive,
        "excluded_prefixes": patterns,
        "all_terms": len(all_terms),
        "excluded_terms": excluded,
        "excluded_count": len(excluded),
        "included_terms": included,
        "included_count": len(included),
        "statistics": {
            "exclusion_rate": round(len(excluded) / len(all_terms), 2) if all_terms else 0.0,
            "included_sample": included[:5],
        },
    }
