"""Document chunk retrieval for Kitbash 2.0 (RAG-lite).

Standalone, core module (repo root, not tools/ sandbox). Implements the
rank + token-budget-truncation half of docs/DESIGN-DOCUMENT_CHUNK_RETRIEVAL_v1.md
using the existing tools/tfidf_ranker. This is the "first stages using existing
tools" slice: it does NOT touch the query orchestrator, document storage, or the
tracer. Those are deferred (see the design doc's Reality Check section).

Pipeline:
    1. chunk_document(text)        -> list[str]            (fixed-size token chunks)
    2. DocumentChunkRetriever.retrieve(query, chunks, budget)
                                   -> list[str]            (TF-IDF rank + truncate)
    3. (caller) inject selected chunks into context

Tokenization: simple str.split() + historical_common.normalize_token_list
(deterministic, fast, no spaCy). The design doc itself says a rough estimate is
fine for 2.0.

Deterministic, stateless, stdlib-only at this layer (tfidf_ranker is also
stdlib-only). Graceful degradation: if tfidf_ranker is unavailable or ranking
fails, retrieve() returns [] rather than raising, so a caller can fall back to
grains/facts alone.
"""
from __future__ import annotations

import sys
import json
from typing import List, Optional, Dict, Any, Sequence

from historical_common import normalize_token_list, normalize_config, base_argparse, write_output, fail

# tfidf_ranker is a tools/ module; import defensively (graceful degrade).
try:
    from tfidf_ranker.core import rank_documents as _rank_documents
    _HAVE_TFIDF = True
except Exception:  # pragma: no cover - depends on tools/ being importable
    _rank_documents = None
    _HAVE_TFIDF = False


# ---------------------------------------------------------------------------
# Piece 1: chunker
# ---------------------------------------------------------------------------

def chunk_document(text: str, chunk_size: int = 500, overlap: int = 0) -> List[str]:
    """Split a document into fixed-size token chunks.

    Args:
        text: Raw document string.
        chunk_size: Target tokens per chunk (default 500, per design doc).
        overlap: Tokens carried from the previous chunk into the next (0 = none).

    Returns:
        List of chunk strings. Empty list for empty/whitespace input.
    """
    tokens = text.split()
    if not tokens:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    step = chunk_size - overlap
    chunks: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        window = tokens[i:i + chunk_size]
        if window:
            chunks.append(" ".join(window))
        i += step
    return chunks


# ---------------------------------------------------------------------------
# Piece 2: retriever
# ---------------------------------------------------------------------------

class DocumentChunkRetriever:
    """Retrieve relevant document chunks for a query via TF-IDF + budget truncate."""

    def __init__(self, context_budget: int = 2000):
        """
        Args:
            context_budget: Max tokens for selected document chunks (rest for
                grains/facts in the caller's context builder).
        """
        self.context_budget = context_budget

    def retrieve(self, query: str, chunks: List[str], context_budget: Optional[int] = None) -> List[str]:
        """Retrieve relevant chunks for a query, truncated to the context budget.

        Args:
            query: User query (string; tokenized internally).
            chunks: List of document chunk strings (e.g. from chunk_document).
            context_budget: Override instance default for this call.

        Returns:
            Selected chunks in score order (highest relevance first), truncated
            so estimated total tokens <= budget. Empty list on no chunks, no
            tfidf_ranker, or ranking failure (graceful degradation).
        """
        budget = context_budget if context_budget is not None else self.context_budget
        if not chunks or not query or not query.strip():
            return []

        # Build corpus dicts the real tfidf_ranker expects: {"id", "tokens"}.
        cfg = normalize_config(None)  # default normalize config (lowercase/stopwords/min-len)
        corpus = [
            {"id": f"chunk_{i}", "tokens": normalize_token_list(c.split(), cfg)}
            for i, c in enumerate(chunks)
        ]
        # Drop chunks that tokenize to nothing (empty/stub).
        corpus = [d for d in corpus if d["tokens"]]
        if not corpus:
            return []

        if not _HAVE_TFIDF:
            return []  # graceful: no ranker available

        try:
            query_tokens = normalize_token_list(query.split(), cfg)
            if not query_tokens:
                return []
            result = _rank_documents(query_tokens, corpus)
            ranking = result.get("ranking", [])
            # ranking: [{"document_id": "chunk_i", "score": s}, ...] already sorted desc.
            selected: List[str] = []
            total_tokens = 0
            id_to_chunk = {f"chunk_{i}": c for i, c in enumerate(chunks)}
            for entry in ranking:
                did = entry.get("document_id")
                chunk = id_to_chunk.get(did)
                if chunk is None:
                    continue
                chunk_tokens = len(chunk) // 4  # ~4 chars/token estimate
                if total_tokens + chunk_tokens <= budget:
                    selected.append(chunk)
                    total_tokens += chunk_tokens
                else:
                    break  # next chunk won't fit; stop (rank order preserves best-first)
            return selected
        except Exception:
            # Never crash the caller's query path on a ranking failure.
            return []


# ---------------------------------------------------------------------------
# Piece 3: CLI entry
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: retrieve relevant chunks from a document for a query.

    Usage:
        python document_retrieval.py --document doc.txt --query "..." [--budget 2000]
                                      [--output-json out.json]
    Output envelope follows tools/historical_common (tool/version/run_id/...).
    """
    ap = base_argparse("document_retrieval")
    ap.description = "Retrieve relevant document chunks via TF-IDF (standalone; no orchestrator wiring)."
    ap.add_argument("--document", required=True, help="Path to a .txt document to chunk + retrieve from")
    ap.add_argument("--query", required=True, help="User query")
    ap.add_argument("--budget", type=int, default=2000, help="Context budget in tokens (default 2000)")
    ap.add_argument("--chunk-size", type=int, default=500, help="Tokens per chunk (default 500)")
    ap.add_argument("--output-json", dest="output", help="Write result JSON to this path (or stdout)")
    args = ap.parse_args(list(argv) if argv is not None else None)

    try:
        with open(args.document, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        return fail("file_error", str(e), 2)

    chunks = chunk_document(text, chunk_size=args.chunk_size)
    retriever = DocumentChunkRetriever(context_budget=args.budget)
    selected = retriever.retrieve(args.query, chunks, context_budget=args.budget)

    total_tokens = sum(len(c) // 4 for c in selected)
    payload: Dict[str, Any] = {
        "query": args.query,
        "context_budget": args.budget,
        "document_chunks_total": len(chunks),
        "selected_count": len(selected),
        "selected_tokens_est": total_tokens,
        "selected_chunks": selected,
        "tfidf_ranker_available": _HAVE_TFIDF,
    }
    write_output(payload, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
