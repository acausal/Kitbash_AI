"""tools.inverted_index_builder — token->document inverted index (see SPEC).

Build a TF/DF inverted index from a document corpus, plus compute_idf and
document-frequency helpers. Stateless, deterministic, stdlib-only.
"""
from .core import build_index, compute_idf, add_document, merge_indexes
from .index_schema import IndexEntry, Posting

__all__ = ["build_index", "compute_idf", "add_document", "merge_indexes",
           "IndexEntry", "Posting"]
