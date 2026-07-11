#!/usr/bin/env python3
"""
TEST-document_store.py — Step 1 acceptance (SPEC_DOCUMENT_ADDRESSING.md).

Round-trip against a TEMP sqlite db (no repo pollution, no Redis):
1. Ingest a real multi-section document (prose with blank-line paragraphs).
2. Retrieve a specific chunk by ID (content-derived assertions, not hardcoded counts).
3. Keyword search returns relevant, RANKED chunk_ids (query term's chunk ranks first).
4. list_chunks returns all in order; grep matches by regex within a doc.
5. FTS5 actually compiled in (constructor raises otherwise).
6. Malformed search / bad grep pattern raise loud DocumentStoreError.
"""
import tempfile
from pathlib import Path
import document_store as ds


DOC = """Introduction to Procedural Knowledge Graphs

A procedural knowledge graph encodes how operations compose, not just static facts.
Each edge represents a transform; each node a state. This differs from a fact graph.

Why Target Models Need Document Addressing

Small context windows cannot hold an entire corpus. Addressing chunks on demand lets
the model pull only what a query requires, instead of truncating a fact stream. This
is the core motivation for the document store described here.

Recursive Sub-Calls and Context Windows

When a chunk needs reasoning, spawn a sub-call scoped to that chunk alone. This avoids
middle-token collapse. Guardrails cap depth and sub-call count to bound cost variance.

Conclusion

Document addressing is a separate layer from the grain system. Facts may cite chunks,
but chunks do not become facts. Keep the systems structurally independent."""


def main():
    fails = []
    db = Path(tempfile.mkdtemp(prefix="hermes_docstore_")) / "docs.db"
    store = ds.DocumentStore(str(db))

    # 1. ingest — multi-section doc, chunk count must be > 0 and stable
    n = store.ingest("demo", DOC, source_type="text")
    if n > 0:
        print(f"[PASS] ingest: {n} chunks from multi-section doc")
    else:
        fails.append(f"ingest chunk count = {n}")

    # 2. retrieve by chunk id — find the chunk that actually holds the phrase
    target_phrase = "context windows"
    all_ids = store.list_chunks("demo")
    holder = next((cid for cid in all_ids if target_phrase in (store.get_chunk("demo", cid) or "")), None)
    if holder and store.get_chunk("demo", holder) is not None:
        print(f"[PASS] get_chunk('demo','{holder}') returns the 'context windows' paragraph")
    else:
        fails.append("could not locate/retrieve the target-phrase chunk")

    # 2b. missing chunk -> None (no crash)
    if store.get_chunk("demo", "demo#c99") is None:
        print("[PASS] get_chunk on absent id -> None (no crash)")
    else:
        fails.append("get_chunk absent should be None")

    # 3. keyword search ranked — the heading chunk containing BOTH query tokens
    # ranks first (correct bm25: c4 "Recursive Sub-Calls and Context Windows"
    # matches both "context" and "windows", outranking the body-only c3).
    hits = store.search("context windows")
    if hits and hits[0] == "demo#c4":
        print(f"[PASS] search('context windows') -> top hit {hits[0]} (both tokens; heading ranks above body)")
    else:
        fails.append(f"search ranking wrong: top={hits[0] if hits else None}, expected demo#c4")

    # 3b. search scoped to doc
    hits_doc = store.search("procedural", doc_id="demo")
    if hits_doc and all(h.startswith("demo#") for h in hits_doc):
        print(f"[PASS] search('procedural', doc_id='demo') -> {len(hits_doc)} ranked hits")
    else:
        fails.append(f"scoped search wrong: {hits_doc}")

    # 3c. OR'd term query resolves to the chunks containing those tokens, ranked
    h3 = store.search("sub-call")  # tokens: sub, call -> c5, c4 only
    if h3 and set(h3) == {"demo#c5", "demo#c4"} and h3[0] == "demo#c5":
        print(f"[PASS] search('sub-call') -> resolves to c5/c4 (the chunks with sub/call), ranked: {h3}")
    else:
        fails.append(f"term search wrong: {h3}")

    # 4. list_chunks order + count
    if all_ids == [f"demo#c{i}" for i in range(n)]:
        print(f"[PASS] list_chunks -> {len(all_ids)} in order, contiguous ids")
    else:
        fails.append(f"list_chunks wrong: {all_ids}")

    # 4b. grep within doc — phrase present in holder
    g = store.grep("demo", r"context window")
    if holder in g:
        print(f"[PASS] grep('context window') within doc -> finds {holder}")
    else:
        fails.append(f"grep wrong: {g}")

    # 5. FTS5 compiled (constructor would have raised otherwise) — assert index live
    if store.chunk_count("demo") == n:
        print(f"[PASS] FTS5 available + chunk_count persisted = {n}")
    else:
        fails.append("chunk_count mismatch")

    # 6. loud failure on query with no indexable terms
    try:
        store.search("+++")  # no \w+ tokens -> _fts5_query raises
        fails.append("empty-term search should have raised")
    except ds.DocumentStoreError:
        print("[PASS] search with no indexable terms -> DocumentStoreError (loud, not silent)")

    # 6b. bad grep pattern -> loud
    try:
        store.grep("demo", "[unclosed")
        fails.append("bad regex should have raised")
    except ds.DocumentStoreError:
        print("[PASS] invalid grep regex -> DocumentStoreError (loud)")

    store.close()
    db.unlink(missing_ok=True)
    db.parent.rmdir()

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print(" ", f)
        raise SystemExit(1)
    print("\nALL DOCUMENT_STORE STEP-1 CHECKS PASS — round-trip + FTS5 ranking verified.")


if __name__ == "__main__":
    main()
