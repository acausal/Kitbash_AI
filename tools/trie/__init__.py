"""tools.trie package.

Library:
    from tools.trie import (
        build_trie, search_trie, prefix_search, suggest_completions,
        negation_search, get_trie_stats, serialize_trie, deserialize_trie,
    )

CLI:
    python -m tools.trie build --vocabulary vocab.jsonl --case-sensitive
    python -m tools.trie search --trie t.json --query photosynthesis
    python -m tools.trie prefix-search --trie t.json --prefix photo
    python -m tools.trie suggest --trie t.json --input pho --max-suggestions 5
    python -m tools.trie negation-search --trie t.json --exclude-patterns '["photo","atp"]'
    python -m tools.trie stats --trie t.json
    python -m tools.trie serialize --trie t.json
    python -m tools.trie deserialize --trie-file t.json

Stdlib only (json, collections). Exit codes: 0 success, 1 ValueError, 2 RuntimeError.
"""
from .core import (
    build_trie, search_trie, prefix_search, suggest_completions, get_trie_stats,
)
from .negation import negation_search
from .serialization import serialize_trie, deserialize_trie
from .trie_node import TrieNode, END

__all__ = [
    "build_trie",
    "search_trie",
    "prefix_search",
    "suggest_completions",
    "negation_search",
    "get_trie_stats",
    "serialize_trie",
    "deserialize_trie",
    "TrieNode",
    "END",
]
