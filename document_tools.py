#!/usr/bin/env python3
"""
document_tools.py — Document Addressing navigation layer (SPEC_DOCUMENT_ADDRESSING.md §2.2).

A fixed, small tool-calling surface the inference engine calls against the storage
layer (document_store.py). Deliberately narrow (vs RLM's free-form REPL) for
reliability at small-model scale — see §3 (both variants get tested before either
is committed to).

Tools (§2.2):
  search(query) -> ranked chunk_ids            (FTS5 lookup)
  get_chunk(document_id, chunk_id) -> content
  list_chunks(document_id) -> [chunk_ids]
  grep(document_id, pattern) -> matching chunk_ids

Design notes:
- Structurally separate from cartridges/grains/facts. A fact MAY cite a chunk_id;
  a chunk does NOT become a fact.
- No Redis dependency, no embeddings (deferred — spec §2.1/§6).
- Tracing (§2.4) is Step 7, NOT implemented here. A `trace_fn` seam is provided so
  Step 7 can wire log_trace() without refactoring the tool logic: trace_fn is called
  as trace_fn(query_id, document_id, chunk_id, tool) on every chunk pull.
- Recursive sub-calls (§2.3): the engine spawns a fresh sub-call scoped to one chunk
  and calls get_chunk() again — that's an engine concern, not this surface. The
  recursion GUARDRAILS (depth/sub-call caps) are TBD from large-model trajectory
  data (Step 4); they are exposed here as config knobs (max_depth, max_sub_calls)
  with conservative placeholders, NOT final values. Step 4 sets the real numbers.
- Loud failure discipline (§5.5): storage errors propagate as DocumentStoreError,
  never swallowed into a bare except.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from document_store import DocumentStore, DocumentStoreError

# §2.3 recursion caps — PLACEHOLDERS only. Step 4 replaces these with values
# derived from large-model trajectory data. Do not treat as tuned.
DEFAULT_MAX_DEPTH = 1
DEFAULT_MAX_SUB_CALLS = 4


class DocumentTools:
    """
    Fixed tool surface over a DocumentStore.

    Args:
        store: a DocumentStore instance (caller owns lifecycle / db path).
        trace_fn: optional callable(query_id, document_id, chunk_id, tool) invoked
            on every chunk pull (Step 7 wires log_trace here). If None, no-op.
        max_depth / max_sub_calls: recursion guardrail knobs (§2.3). Placeholders;
            Step 4 sets real values from trajectory data.
    """

    def __init__(
        self,
        store: DocumentStore,
        trace_fn: Optional[Callable[[str, str, str, str], None]] = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_sub_calls: int = DEFAULT_MAX_SUB_CALLS,
    ):
        self.store = store
        self.trace_fn = trace_fn
        self.max_depth = max_depth
        self.max_sub_calls = max_sub_calls

    # ------------------------------------------------------------ the four tools
    def search(self, query: str, document_id: Optional[str] = None) -> List[str]:
        """FTS5 keyword search -> ranked chunk_ids (across all docs, or one)."""
        return self.store.search(query, doc_id=document_id)

    def list_chunks(self, document_id: str) -> List[str]:
        """All chunk_ids for a document, in order."""
        return self.store.list_chunks(document_id)

    def grep(self, document_id: str, pattern: str) -> List[str]:
        """Chunk_ids within a document whose content matches the regex `pattern`."""
        return self.store.grep(document_id, pattern)

    def get_chunk(self, document_id: str, chunk_id: str,
                  query_id: str = "unspecified") -> Optional[str]:
        """
        Retrieve one chunk's content. This is the primitive a recursive sub-call
        uses when scoped to a single chunk (§2.3).

        Every successful pull fires trace_fn (Step 7 seam). Missing chunk -> None
        (loud-free absence, consistent with store.get_chunk).
        """
        content = self.store.get_chunk(document_id, chunk_id)
        if content is not None and self.trace_fn is not None:
            self.trace_fn(query_id, document_id, chunk_id, "get_chunk")
        return content

    # ------------------------------------------------------------ recursion guard
    def sub_call_budget_ok(self, depth: int, sub_calls_used: int) -> bool:
        """
        Guardrail check for the engine's recursive sub-call loop (§2.3).
        Returns False if depth or sub-call count would exceed the configured caps.
        PLACEHOLDER caps until Step 4 sets real values from trajectory data.
        """
        return depth <= self.max_depth and sub_calls_used < self.max_sub_calls


def make_tools(db_path: str = "data/document_store/docs.db",
               trace_fn: Optional[Callable[[str, str, str, str], None]] = None,
               max_depth: int = DEFAULT_MAX_DEPTH,
               max_sub_calls: int = DEFAULT_MAX_SUB_CALLS) -> DocumentTools:
    """Convenience factory: open a DocumentStore and wrap it in DocumentTools."""
    return DocumentTools(DocumentStore(db_path), trace_fn=trace_fn,
                         max_depth=max_depth, max_sub_calls=max_sub_calls)
