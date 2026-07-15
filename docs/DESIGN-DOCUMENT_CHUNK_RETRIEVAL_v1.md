# Design: Document Chunk Retrieval for 2.0
**Date:** July 15, 2026  
**Status:** Design phase (ready for implementation in Phase B2)  
**Scope:** Simple but thoughtful retrieval for uploaded documents  
**Approach:** TF-IDF ranking + context budget truncation  
**Philosophy:** Not perfect, but better than naive approaches

---

## Problem

User uploads a document. System chunks it (500 tokens per chunk, fixed size). On query, need to retrieve the ~5–10 most relevant chunks to inject into BitNet's context.

**Constraints:**
- Context window is limited (BitNet + grains/facts + document chunks must all fit)
- Retrieval must be fast (sub-100ms ideal, can't slow down queries)
- No semantic embeddings for chunks (they're not in the grain system yet)
- Should work well enough to let users test the feature

**Non-goals for 2.0:**
- Perfect relevance (this is RAG lite, not production RAG)
- Semantic similarity (that's 2.1+)
- Deduplication with existing grains (retrieve independently)
- Query rewriting or expansion
- Multi-document retrieval (one document at a time)

---

## Approach: TF-IDF + Truncation

### Why TF-IDF?

**Available tools:** You have `tfidf_ranker` (built and tested)

**Why it wins for this use case:**
- No embeddings needed (chunks aren't in the grain system)
- Fast (linear in chunk count, document is ~50–500 chunks)
- Reasonable quality (captures term importance)
- Deterministic (same query always ranks same)
- Interpretable (users can see why a chunk ranked high)

**Why not semantic (cosine_similarity)?**
- Requires embeddings for chunks (adds complexity)
- Chunks aren't in the cartridge system yet (no existing vectors)
- Would need to embed on-query (latency hit)
- Overkill for 2.0 (2.1 can add this)

**Why not boolean_search?**
- Nice to have (advanced users could query "sections about X AND Y")
- Not necessary for 2.0 (TF-IDF handles basic relevance)
- Defer to 2.1 if users ask for it

### The Algorithm

```
Input: query (string), chunks (list of strings), context_budget (tokens)
Output: list of chunks, ordered by relevance, truncated to fit budget

Step 1: Score chunks with TF-IDF
  For each chunk, compute relevance score based on query terms
  Return ranking: [(chunk_index, score), ...]

Step 2: Sort by score
  Highest scores first

Step 3: Truncate to context budget
  Iterate through sorted chunks
  Add chunk if it fits in remaining budget
  Stop when next chunk would overflow

Step 4: Return selected chunks
  In rank order (highest relevance first)
```

---

## Implementation Design

### File Structure

```
kitbash/
  query_orchestrator.py (existing)
  document_retrieval.py (new)
    - DocumentChunkRetriever class
    - retrieve(query, chunks, context_budget) → list[str]
```

### DocumentChunkRetriever Class

```python
from tfidf_ranker import score_documents  # Import your existing tool

class DocumentChunkRetriever:
    """Retrieve relevant chunks from a document."""
    
    def __init__(self, context_budget: int = 2000):
        """
        Args:
            context_budget: Max tokens for document chunks in context (rest for grains/facts)
        """
        self.context_budget = context_budget
    
    def retrieve(self, query: str, chunks: list[str]) -> list[str]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query (string)
            chunks: List of document chunks (strings)
        
        Returns:
            List of chunks, ranked by relevance, truncated to context budget
        """
        if not chunks:
            return []
        
        # Step 1: Score chunks with TF-IDF
        scores = score_documents(
            query=query,
            documents=chunks,
        )  # Returns list of (doc_index, score) tuples
        
        # Step 2: Sort by score (descending)
        sorted_chunks = sorted(scores, key=lambda x: x[1], reverse=True)
        
        # Step 3: Truncate to context budget
        selected = []
        total_tokens = 0
        
        for chunk_idx, score in sorted_chunks:
            chunk = chunks[chunk_idx]
            chunk_tokens = self._estimate_tokens(chunk)
            
            if total_tokens + chunk_tokens <= self.context_budget:
                selected.append(chunk)
                total_tokens += chunk_tokens
            else:
                # Next chunk doesn't fit; stop
                break
        
        return selected
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token count (not exact, but good enough).
        Rule of thumb: ~4 characters per token.
        """
        return len(text) // 4
```

### Integration into Query Orchestrator

**Where it fits:**

```
User query
  ↓
Load active document (if any)
  ↓
Chunk retrieval (TF-IDF rank + truncate)  ← NEW STEP
  ↓
Grain/fact retrieval (existing)
  ↓
Context builder (combine grains + facts + document chunks)  ← MODIFIED
  ↓
BitNet inference
  ↓
Response
```

**Code change (sketch):**

```python
def finalize_query(query: str):
    """Execute query with document retrieval."""
    
    # Existing: retrieve grains + facts
    grains = cartridge_loader.retrieve(query)
    facts = grain_router.rank(grains)
    
    # NEW: retrieve document chunks (if document active)
    document_chunks = []
    if has_active_document():
        doc_chunks_all = get_active_document_chunks()
        retriever = DocumentChunkRetriever(context_budget=2000)
        document_chunks = retriever.retrieve(query, doc_chunks_all)
    
    # Existing: build context (grains + facts)
    # MODIFIED: also include document chunks
    context = context_builder.build(
        grains=grains,
        facts=facts,
        document_chunks=document_chunks,  # NEW
    )
    
    # Existing: inference
    response = bitnet.generate(context)
    
    return response
```

---

## Design Decisions & Tradeoffs

### Decision 1: Context Budget Allocation

**Current proposal:** Allocate ~2000 tokens for document chunks, rest for grains/facts

**Rationale:**
- BitNet context window is ~4000 tokens (rough, adjust per your setup)
- Grains/facts + system prompt need ~1500–2000 tokens
- Leaves ~2000 for document chunks (roughly 4–5 chunks at 400 tokens each)

**Tunable:** Users could control this (e.g., "prioritize document" vs. "prioritize grains"). Defer to 2.1.

### Decision 2: Rank Order

**Current proposal:** Return chunks in score order (highest relevance first)

**Rationale:**
- If context gets truncated, at least the highest-relevance chunks made it in
- Context builder can then choose: "prepend document chunks" or "interleave with grains"

**Alternative:** Return chunks in document order (preserve reading flow)
- Pro: Reads more naturally
- Con: Irrelevant chunks at start waste tokens
- Recommendation: Score order for 2.0, offer document-order option in 2.1

### Decision 3: Retrieve Independently (vs. Dedup with Grains)

**Current proposal:** Retrieve document chunks independently. Don't check if grains already covered this content.

**Rationale:**
- Simpler implementation (no cross-system dedup logic)
- Grains and document chunks are different systems (grains are crystallized knowledge, chunks are ephemeral)
- Trade-off: Slight redundancy in context (acceptable for 2.0)

**Future revisit:** Post-2.0, could add dedup layer ("don't include chunk if grain already says this")
- Would need semantic similarity check (cosine_similarity tool available, but adds latency)
- Worthwhile once you have more usage data

### Decision 4: TF-IDF Config

**Proposed defaults:**
- Term weighting: TF-IDF (existing tool default)
- Minimum chunk size: ~100 tokens (skip empty/stub chunks)
- Case-insensitive: Yes (normalize query + chunks)

**Tunable later:** Term frequency weights, IDF smoothing, chunk filtering rules

---

## Testing & Validation

### Unit Tests (before integration)

```python
def test_retrieval_ranks_by_relevance():
    """Relevant chunks rank higher."""
    chunks = [
        "The cat sat on the mat.",
        "Photosynthesis is how plants make energy.",
        "The dog played in the garden.",
    ]
    query = "plants energy"
    
    retriever = DocumentChunkRetriever()
    result = retriever.retrieve(query, chunks)
    
    # Should rank chunk[1] highest (plants + energy)
    assert result[0] == chunks[1]

def test_retrieval_respects_context_budget():
    """Doesn't exceed context budget."""
    chunks = ["A" * 1000, "B" * 1000, "C" * 1000, "D" * 1000]
    query = "test"
    
    retriever = DocumentChunkRetriever(context_budget=2500)
    result = retriever.retrieve(query, chunks)
    
    total_tokens = sum(len(c) // 4 for c in result)
    assert total_tokens <= 2500

def test_retrieval_empty_document():
    """Handles empty chunk list."""
    retriever = DocumentChunkRetriever()
    result = retriever.retrieve("query", [])
    assert result == []
```

### Integration Tests (after wiring into orchestrator)

```python
def test_e2e_query_with_document():
    """Query with active document returns response referencing it."""
    doc = "The capital of France is Paris."
    upload_document(doc)
    
    response = query("What's the capital of France?")
    
    assert "Paris" in response  # Should reference document

def test_e2e_document_chunks_in_context():
    """Document chunks actually make it into BitNet's context."""
    doc = "Photosynthesis converts light into chemical energy."
    upload_document(doc)
    
    # Query that should retrieve this chunk
    trace = query_with_trace("How do plants convert light?")
    
    # Check execution trace: document chunks were included
    assert "document_chunks" in trace["context_builder_output"]
    assert len(trace["context_builder_output"]["document_chunks"]) > 0
```

---

## Known Limitations & Future Work

### 2.0 Limitations (acceptable for alpha)

1. **No semantic relevance** — TF-IDF is keyword-based. "power plants" and "energy sources" won't cross-match. (2.1: add semantic ranking)

2. **No deduplication** — If a grain says "Paris is the capital of France" and the document says the same thing, both appear in context. (2.1: add dedup layer)

3. **No multi-document** — One document at a time. (2.1: queue multiple documents)

4. **No query expansion** — Won't match synonyms. "What's the biggest city?" won't retrieve chunks about "largest metropolis." (2.1: add query expansion)

5. **No chunk context** — Chunks are independent. Might break mid-sentence if boundaries don't align. (2.0+: better chunking strategy)

### Future Enhancements (Post-2.0)

| Feature | When | Effort | Benefit |
|---------|------|--------|---------|
| Semantic ranking (cosine_similarity) | 2.1 | Medium | Better relevance on synonyms |
| Deduplication with grains | 2.1 | Medium | Smaller context, less redundancy |
| Boolean queries (boolean_search) | 2.1 | Low | Advanced users can refine retrieval |
| Query expansion (synonym detection) | 2.1+ | Medium | "Biggest" matches "largest" |
| Smart chunking (sentence/paragraph boundaries) | 2.1+ | Medium | Better coherence, fewer mid-sentence breaks |
| Multi-document retrieval | 2.1+ | Low | Stack multiple documents in context |
| Document indexing (inverted_index_builder) | 2.1+ | Low | Speed up repeated queries on same document |

---

## Configuration & User Control

### 2.0 (Fixed)
- Context budget: 2000 tokens (hardcoded)
- Ranking: TF-IDF (only option)
- Dedup: Off (document chunks retrieved independently)

### 2.1+ (Tunable)
- Context budget: User slider (e.g., "prioritize document" → 3000 tokens, "prioritize grains" → 1000 tokens)
- Ranking: Option for document-order or score-order
- Dedup: Toggle on/off
- Query expansion: On/off
- Chunking strategy: Fixed size or smart boundaries

---

## Metrics & Monitoring

### Collect During 2.0

Track per-query (add to execution trace):
- Number of chunks retrieved
- Total tokens used for document chunks
- Top chunk score (relevance of best match)
- Did response reference document content? (heuristic: count overlapping words)

### Questions to Answer Post-2.0

- How often do document chunks appear in responses? (0–100%)
- Do users find the retrieved chunks relevant? (manual review of ~50 queries)
- Does including document chunks improve response quality? (A/B test: with vs. without)
- Is context budget allocation right? (enough room for documents, but not squeezing grains)

---

## Implementation Checklist

- [ ] Create `document_retrieval.py` with `DocumentChunkRetriever` class
- [ ] Write unit tests (retrieval ranking, context budget, empty case)
- [ ] Wire into `query_orchestrator.py` (add document chunk retrieval step)  ← BLOCKED (see Reality Check)
- [ ] Modify `context_builder` to accept and inject document chunks  ← BLOCKED (see Reality Check)
- [ ] Update execution tracer to log document retrieval results  ← DEFERRED
- [ ] Manual integration test: upload doc → query → response references it  ← BLOCKED (no doc store)
- [ ] Document limitations + future work (in this design doc)
- [ ] Add metrics collection (for post-2.0 analysis)

---

## Implementation Reality Check (Audited 2026-07-15)

The design above was written against an idealized/stale layout. Audited against
the actual repo before building. Findings below are source-verified, not inferred.

### Real `tfidf_ranker` API (the doc's `score_documents` is wrong on 3 axes)
The actual tool is `tools/tfidf_ranker/core.py`:

```python
def rank_documents(query: Sequence[str], corpus: Sequence[dict], config: dict = None) -> dict:
    # query  = LIST OF TOKENS (not a raw string)
    # corpus = list of dicts, each MUST carry {"id": ..., "tokens": [...]}  (pre-tokenized)
    # returns dict with ranking: [{"document_id": did, "score": s}, ...]  (sorted desc)
```

Deviations from the design doc's assumed `score_documents(query, documents) -> list[(index, score)]`:
1. Function is `rank_documents`, not `score_documents`.
2. `query` is a **token list**, not a string — caller tokenizes first.
3. `corpus` entries are **dicts with a `tokens` key**, not raw strings; and the
   ranking is keyed by `document_id`, not list index.
4. Return is a **dict** (`result["ranking"]`), not a list of tuples.

`normalize_corpus` (in `tools/historical_common.py`) only *filters* tokens
(lowercase/stopwords/min-length) — it does **not** tokenize raw text. So chunk
preparation must produce `{"id": "chunk_0", "tokens": [...]}`, where tokens come
from a basic split + `normalize_token_list`. (spaCy tokenizer is more accurate but
needs the `PYTHONPATH=` venv trick; `.split()` is deterministic + fast for 2.0.)

### Components that DO NOT exist (blockers for "actual loop" wiring)
- `upload_document`, `has_active_document`, `get_active_document_chunks` — **no
  document upload/storage layer exists at all**. The design hand-waves this
  ("if has_active_document()"). Real wiring requires inventing storage first.
- `context_builder` module — **does not exist** as a file. The orchestrator
  builds the engine prompt from `augmented_query` inside `query_orchestrator_posix.py`;
  there is no standalone `context_builder.build(grains, facts, document_chunks)`.
  Wiring means injecting retrieved chunks into prompt construction in the
  orchestrator, not "modifying context_builder".
- Wiring target: live orchestrator is `query_orchestrator_posix.py` (root
  `query_orchestrator.py` is retired to `attic/`), not `kitbash/query_orchestrator.py`.
- File path `kitbash/document_retrieval.py` — repo is flat; a core module lands at
  repo root (matching the orchestrator), not under `kitbash/`.

### What IS feasible to build NOW (standalone, using existing tools)
The core algorithm — chunk → TF-IDF rank → token-budget truncation — is fully
buildable and testable with **no document-upload dependency**:
1. **Chunker**: split a document string into fixed-size token chunks, each
   `{"id": "chunk_N", "tokens": [...]}`.
2. **`DocumentChunkRetriever`**: tokenize query, build corpus dicts, call real
   `rank_documents`, sort, truncate to `context_budget` (token-estimate ~len//4).
   Adapted from the doc's class to the real API.
3. **`document_retrieval.py`** (repo root) combining 1+2, with a function/CLI
   entry, verified by an ad-hoc gate on a sample doc.

### Deferred until "actual loop" decision (post-2.0 / Phase B2)
- Orchestrator wiring + document storage/upload.
- Tracer/metrics injection.
- Multi-doc, dedup, semantic ranking, query expansion, smart chunking — per doc,
  all 2.1+.

**Decision (2026-07-15):** build pieces 1–3 as a standalone, tested module now;
defer orchestrator integration + storage to a later, separate decision.

---

## Notes for Implementation

1. **Token estimation:** Current proposal is `len(text) // 4`. You can refine this later (spaCy tokenizer would be more accurate, but slower). For 2.0, rough estimate is fine.

2. **TF-IDF tool usage:** Verify `tfidf_ranker.score_documents(query, documents)` returns `list[(index, score)]`. If API is different, adapt accordingly.

3. **Context builder changes:** Currently takes grains + facts. Will need to accept optional `document_chunks` parameter. Non-breaking change (default to empty list).

4. **Error handling:** If TF-IDF fails (empty query, very large document), should gracefully degrade (return empty chunk list, continue with grains/facts alone). Never crash on bad document.

5. **Performance:** With 500-chunk document, TF-IDF ranking should take <50ms. If slower, consider caching scores or pruning chunk count.

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | Jul 15 2026 | Initial design: TF-IDF + truncation |

---

**Version:** 1.0  
**Author:** Claude (design) + Isaac (product vision)  
**For:** Kitbash 2.0 Phase B2 implementation  
**Date:** July 15, 2026
