"""tools.boolean_search core (stdlib only).

Parse a boolean query into an AST, evaluate it against documents (token sets),
and search a corpus. See SPEC-boolean_search_v1.md.

Output shape (from SPEC):
  {
    "tool": "boolean_search", "version": "v1", "run_id", "timestamp",
    "input_summary": {"query": str, "documents": N, "matching_documents": M,
                      "parse_success": bool},
    "parsed_query": <AST as nested dict>,
    "results": [{"document_id":..., "matched": true, "score": int,
                 "matched_terms": [...], "missing_terms": [...]}],
    "metadata": {...}
  }
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from tools.historical_common import normalize_config, normalize_corpus, now_iso
from .query_parser import Parser
from .search_schema import QueryNode


def _rid(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _ast_to_dict(node: QueryNode) -> dict:
    if node.op == "TERM":
        return {"op": "TERM", "term": node.term}
    d = {"op": node.op}
    if node.left is not None:
        d["left"] = _ast_to_dict(node.left)
    if node.right is not None:
        d["right"] = _ast_to_dict(node.right)
    return d


def parse_query(query: str, config: dict = None) -> dict:
    """Parse a query string into an AST dict. Raises ValueError on syntax error."""
    _ = normalize_config(config)  # honor shared config for consistency
    ast = Parser(query).parse()
    return {"tool": "boolean_search", "version": "v1", "run_id": _rid("bs_parse"),
            "timestamp": now_iso(),
            "input_summary": {"query": query, "parse_success": True},
            "parsed_query": _ast_to_dict(ast),
            "metadata": {"computation_time_ms": 0}}


def _eval(node: QueryNode, doc_tokens: Set[str], matched: Set[str], missing: Set[str]) -> bool:
    if node.op == "TERM":
        if node.term in doc_tokens:
            matched.add(node.term)
            return True
        missing.add(node.term)
        return False
    if node.op == "NOT":
        return not _eval(node.left, doc_tokens, matched, missing)
    if node.op == "AND":
        return _eval(node.left, doc_tokens, matched, missing) and _eval(node.right, doc_tokens, matched, missing)
    if node.op == "OR":
        return _eval(node.left, doc_tokens, matched, missing) or _eval(node.right, doc_tokens, matched, missing)
    raise ValueError(f"unknown op {node.op}")


def execute_query(query_ast: dict, document_tokens: Sequence[str], config: dict = None) -> dict:
    """Evaluate a parsed AST (from parse_query) against one document's tokens."""
    _ = normalize_config(config)
    node = _dict_to_node(query_ast)
    doc_set = set(document_tokens)
    matched: Set[str] = set()
    missing: Set[str] = set()
    res = _eval(node, doc_set, matched, missing)
    return {"matched": res, "matched_terms": sorted(matched),
            "missing_terms": sorted(missing)}


def _dict_to_node(d: dict) -> QueryNode:
    if d["op"] == "TERM":
        return QueryNode(op="TERM", term=d["term"])
    n = QueryNode(op=d["op"])
    n.left = _dict_to_node(d["left"]) if "left" in d else None
    n.right = _dict_to_node(d["right"]) if "right" in d else None
    return n


def search(query: str, corpus: Sequence[dict], config: dict = None) -> dict:
    """Search a tokenized corpus with a boolean query. Returns matches + scores."""
    cfg = normalize_config(config)
    ast = Parser(query).parse()
    norm = normalize_corpus(corpus, cfg)

    def doc_set(d: dict) -> Set[str]:
        return set(d.get("tokens", []))

    results = []
    for doc in norm:
        matched: Set[str] = set()
        missing: Set[str] = set()
        ok = _eval(ast, doc_set(doc), matched, missing)
        if ok:
            # score = number of distinct matched TERM leaves
            results.append({
                "document_id": doc.get("id", ""),
                "matched": True,
                "score": len(matched),
                "matched_terms": sorted(matched),
                "missing_terms": sorted(missing),
            })
    results.sort(key=lambda r: (-r["score"], r["document_id"]))
    return {
        "tool": "boolean_search", "version": "v1", "run_id": _rid("bs"),
        "timestamp": now_iso(),
        "input_summary": {
            "query": query,
            "documents": len(norm),
            "matching_documents": len(results),
            "parse_success": True,
        },
        "parsed_query": _ast_to_dict(ast),
        "results": results,
        "metadata": {"computation_time_ms": 0, "config_used": cfg},
    }
