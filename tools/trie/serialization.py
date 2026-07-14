"""Serialization helpers for tools.trie (stdlib only)."""
import json
from typing import Dict

from .trie_node import TrieNode, END


def serialize_trie(trie: dict) -> dict:
    """Wrap a nested-dict trie for JSON serialization (already encodable)."""
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    return {
        "trie_json": trie,
        "serialization_params": {
            "format": "nested_dict",
            "encodable": True,
        },
    }


def deserialize_trie(trie_json: str) -> dict:
    """Parse a JSON string back into a trie dict, validating structure."""
    if not isinstance(trie_json, str):
        raise ValueError("deserialize_trie expects a JSON string")
    try:
        obj = json.loads(trie_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("deserialized trie is not a dict")
    # structural sanity: rebuild via TrieNode to ensure it's a valid trie
    node = TrieNode.from_dict(obj)
    restored = node.to_dict()
    return {
        "trie": restored,
        "validation": {
            "valid": True,
            "node_count": _count(restored),
            "vocabulary_retained": len(_words(restored)),
        },
    }


def _count(trie: dict) -> int:
    if not isinstance(trie, dict):
        return 0
    total = 1
    for ch, child in trie.items():
        if ch == END:
            continue
        total += _count(child)
    return total


def _words(trie: dict) -> list:
    out = []
    def walk(node, prefix):
        if not isinstance(node, dict):
            return
        if node.get(END):
            out.append(prefix)
        for ch, child in node.items():
            if ch == END:
                continue
            walk(child, prefix + ch)
    walk(trie, "")
    return out
