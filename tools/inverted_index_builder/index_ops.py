"""tools.inverted_index_builder index operations (stdlib only).

Secondary helpers listed in the SPEC module layout: simple lookups and merges
over an already-built index. Core construction lives in core.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence


def get_postings(index: dict, token: str) -> List[dict]:
    return list(index.get("index", {}).get(token, {}).get("postings", []))


def document_frequency(index: dict, token: str) -> int:
    return index.get("index", {}).get(token, {}).get("document_frequency", 0)


def tokens_in_document(index: dict, doc_id: str) -> List[str]:
    """All tokens that post to a given document (reconstructed from postings)."""
    out = []
    for tok, entry in index.get("index", {}).items():
        for p in entry.get("postings", []):
            if p.get("doc_id") == doc_id:
                out.append(tok)
                break
    return out


__all__ = ["get_postings", "document_frequency", "tokens_in_document"]
