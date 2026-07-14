"""Core trie operations for tools.trie (stdlib only).

The trie is represented as a nested dict (see trie_node.TrieNode.to_dict):
each character is a key; a terminal node carries the END marker as a child.
All query functions operate directly on the nested dict.
"""
from typing import Dict, List, Optional

from .trie_node import END, TrieNode


def _norm(word: str, case_sensitive: bool) -> str:
    return word if case_sensitive else word.lower()


def build_trie(vocabulary: List[str], case_sensitive: bool = True) -> dict:
    if not isinstance(vocabulary, list) or len(vocabulary) == 0:
        raise ValueError("vocabulary must be a non-empty list")
    root = TrieNode()
    normed = []
    for w in vocabulary:
        if not isinstance(w, str):
            raise ValueError(f"vocabulary contains non-string: {w!r}")
        if w == "":
            raise ValueError("vocabulary contains empty string")
        nw = _norm(w, case_sensitive)
        normed.append(nw)
        root.insert(nw)
    trie = root.to_dict()
    nodes = _node_count(trie)
    depth = _max_depth(trie)
    return {
        "build_params": {
            "vocabulary_size": len(normed),
            "case_sensitive": case_sensitive,
        },
        "trie_stats": {
            "node_count": nodes,
            "trie_depth": depth,
            "avg_branch_factor": round(nodes / max(len(normed), 1), 2),
            "vocabulary_retained": len(normed),
        },
        "trie": trie,
        "metadata": {
            "vocabulary_sample": normed[:3],
            "completeness": 1.0,
        },
    }


def _descend(trie: dict, prefix: str, case_sensitive: bool):
    """Return the subtree dict at the end of `prefix`, or None if not found."""
    node = trie
    for ch in _norm(prefix, case_sensitive):
        if not isinstance(node, dict) or ch not in node:
            return None
        node = node[ch]
    return node


def _collect(node: dict, prefix: str, out: List[str]) -> None:
    """DFS from `node`, accumulating `prefix`, recording complete words."""
    if not isinstance(node, dict):
        return
    if node.get(END):
        out.append(prefix)
    for ch, child in node.items():
        if ch == END:
            continue
        _collect(child, prefix + ch, out)


def search_trie(trie: dict, query: str, case_sensitive: bool = True) -> dict:
    if not isinstance(query, str) or query == "":
        raise ValueError("query must be a non-empty string")
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    node = _descend(trie, query, case_sensitive)
    found = node is not None and isinstance(node, dict) and node.get(END, False)
    return {
        "query": query,
        "case_sensitive": case_sensitive,
        "found": bool(found),
        "is_terminal": bool(found),
        "path_traversed": "→".join(_norm(query, case_sensitive)),
        "statistics": {
            "depth_traversed": len(_norm(query, case_sensitive)),
            "nodes_visited": len(_norm(query, case_sensitive)),
            "trie_size": _node_count(trie),
        },
    }


def prefix_search(trie: dict, prefix: str, case_sensitive: bool = True,
                  max_results: Optional[int] = None) -> dict:
    if not isinstance(prefix, str) or prefix == "":
        raise ValueError("prefix must be a non-empty string")
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    subtree = _descend(trie, prefix, case_sensitive)
    matches: List[str] = []
    if subtree is not None:
        _collect(subtree, _norm(prefix, case_sensitive), matches)
    truncated = False
    if max_results is not None and len(matches) > max_results:
        matches = matches[:max_results]
        truncated = True
    return {
        "prefix": prefix,
        "case_sensitive": case_sensitive,
        "matches": matches,
        "match_count": len(matches),
        "truncated": truncated,
        "statistics": {
            "depth_at_prefix_end": len(_norm(prefix, case_sensitive)),
            "subtree_size": len(matches),
        },
    }


def suggest_completions(trie: dict, prefix: str, case_sensitive: bool = True,
                         max_suggestions: int = 10) -> dict:
    if not isinstance(prefix, str) or prefix == "":
        raise ValueError("prefix must be a non-empty string")
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    subtree = _descend(trie, prefix, case_sensitive)
    completions: List[str] = []
    if subtree is not None:
        _collect(subtree, _norm(prefix, case_sensitive), completions)
    suggestions = [{
        "rank": i + 1,
        "completion": c,
        "suffix": c[len(_norm(prefix, case_sensitive)):],
        "confidence": 1.0,
    } for i, c in enumerate(completions[:max_suggestions])]
    return {
        "user_input": prefix,
        "case_sensitive": case_sensitive,
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
        "statistics": {
            "prefix_unique": len(completions) == 1,
            "avg_suggestion_length": (
                round(sum(len(c) for c in completions) / len(completions), 2)
                if completions else 0.0),
        },
    }


def _node_count(trie: dict) -> int:
    """Count all dict nodes (including the root)."""
    if not isinstance(trie, dict):
        return 0
    total = 1
    for ch, child in trie.items():
        if ch == END:
            continue
        total += _node_count(child)
    return total


def _max_depth(trie: dict, depth: int = 0) -> int:
    """Longest word length (depth) in the trie."""
    if not isinstance(trie, dict):
        return depth
    best = depth if trie.get(END) else 0
    for ch, child in trie.items():
        if ch == END:
            continue
        best = max(best, _max_depth(child, depth + 1))
    return best


def _all_words(trie: dict) -> List[str]:
    out: List[str] = []
    _collect(trie, "", out)
    return out


def get_trie_stats(trie: dict) -> dict:
    if not isinstance(trie, dict):
        raise ValueError("invalid trie structure")
    words = _all_words(trie)
    depths = [len(w) for w in words]
    nodes = _node_count(trie)
    internal = 0
    leaves = 0

    def walk(node):
        nonlocal internal, leaves
        if not isinstance(node, dict):
            return
        has_child = False
        for ch, child in node.items():
            if ch == END:
                continue
            has_child = True
            walk(child)
        if has_child:
            internal += 1
        else:
            leaves += 1

    walk(trie)
    max_depth = max(depths) if depths else 0
    min_depth = min(depths) if depths else 0
    avg_depth = round(sum(depths) / len(depths), 2) if depths else 0.0
    branch_counts = []

    def branch(node):
        if not isinstance(node, dict):
            return
        nchildren = len([k for k in node if k != END])
        if nchildren > 0:
            branch_counts.append(nchildren)
        for ch, child in node.items():
            if ch == END:
                continue
            branch(child)

    branch(trie)
    branch_avg = round(sum(branch_counts) / len(branch_counts), 2) if branch_counts else 0.0
    branch_max = max(branch_counts) if branch_counts else 0
    return {
        "trie_statistics": {
            "node_count": nodes,
            "max_depth": max_depth,
            "min_depth": min_depth,
            "avg_depth": avg_depth,
            "vocabulary_size": len(words),
            "branch_factor_max": branch_max,
            "branch_factor_avg": branch_avg,
            "branching_nodes": internal,
            "leaf_nodes": leaves,
            "internal_nodes": internal,
        },
        "memory_estimate_bytes": nodes * 56,
        "sparsity": round(1.0 - (len(words) / max(nodes, 1)), 2),
        "size_interpretation": "compact" if nodes < 100 else "large",
    }
