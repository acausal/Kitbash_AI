"""tools.tfidf_ranker — TF-IDF scoring + cosine ranking (see SPEC).

Compute TF-IDF vectors for a corpus, rank documents against a query by cosine
similarity (with standard / sublinear / BM25 TF variants). Stateless,
deterministic, stdlib-only.
"""
from .core import rank_documents, compute_tfidf, cosine_similarity, bm25_score
from .tfidf_schema import TfidfDoc

__all__ = ["rank_documents", "compute_tfidf", "cosine_similarity", "bm25_score",
           "TfidfDoc"]
