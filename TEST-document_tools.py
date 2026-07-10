#!/usr/bin/env python3
"""
TEST-document_tools.py — Step 2 acceptance (SPEC_DOCUMENT_ADDRESSING.md).

Unit tests for each of the four fixed tools in isolation, plus the recursion-guard
placeholder check and the trace seam (Step 7 hook fires; tracing itself is Step 7).
Uses a TEMP DocumentStore (no repo pollution, no Redis).
"""
import tempfile
from pathlib import Path
import document_store as ds
import document_tools as dt


DOC_A = """Alpha section one

Alpha body text about procedural graphs and composition.

Alpha section two

More alpha content covering context windows and small models."""

DOC_B = """Beta report

Beta discusses recursive sub-calls and guardrails against cost variance.

Beta appendix

Beta appendix mentions facts and grains but not chunks becoming facts."""


def main():
    fails = []
    db = Path(tempfile.mkdtemp(prefix="hermes_doctools_")) / "docs.db"
    store = ds.DocumentStore(str(db))
    store.ingest("docA", DOC_A, source_type="text")
    store.ingest("docB", DOC_B, source_type="text")

    traces = []
    def trace_fn(qid, did, cid, tool):
        traces.append((qid, did, cid, tool))

    tools = dt.DocumentTools(store, trace_fn=trace_fn)

    # --- search (all docs) ranked
    hits = tools.search("context windows")
    if hits and "docA#c3" in hits and hits[0] == "docA#c3":
        print(f"[PASS] search('context windows') -> top {hits[0]} (ranked, scoped none)")
    else:
        fails.append(f"search all-docs wrong: {hits}")

    # --- search scoped to one doc
    hits_b = tools.search("beta", document_id="docB")
    if hits_b and all(h.startswith("docB#") for h in hits_b):
        print(f"[PASS] search('beta', doc_id='docB') -> {len(hits_b)} docB hits")
    else:
        fails.append(f"search scoped wrong: {hits_b}")

    # --- get_chunk returns content + fires trace seam
    c = tools.get_chunk("docA", "docA#c0", query_id="q1")
    if c and "Alpha section one" in c and ("q1", "docA", "docA#c0", "get_chunk") in traces:
        print("[PASS] get_chunk returns content AND fires trace_fn seam (q1/docA/docA#c0)")
    else:
        fails.append(f"get_chunk/trace wrong: content={bool(c)} traces={traces}")

    # --- get_chunk absent -> None, no trace
    before = len(traces)
    miss = tools.get_chunk("docA", "docA#c99", query_id="q2")
    if miss is None and len(traces) == before:
        print("[PASS] get_chunk absent -> None, no trace fired")
    else:
        fails.append(f"get_chunk absent wrong: {miss}, traces_delta={len(traces)-before}")

    # --- list_chunks in order
    lc = tools.list_chunks("docA")
    if lc and lc[0] == "docA#c0" and lc == [f"docA#c{i}" for i in range(len(lc))]:
        print(f"[PASS] list_chunks('docA') -> {len(lc)} in order")
    else:
        fails.append(f"list_chunks wrong: {lc}")

    # --- grep within doc
    g = tools.grep("docB", r"recursive|guardrails")
    if "docB#c1" in g:
        print(f"[PASS] grep('recursive|guardrails','docB') -> {g}")
    else:
        fails.append(f"grep wrong: {g}")

    # --- recursion guard placeholder check
    if tools.sub_call_budget_ok(1, 0) and not tools.sub_call_budget_ok(2, 0) \
       and not tools.sub_call_budget_ok(1, tools.max_sub_calls):
        print(f"[PASS] sub_call_budget_ok enforces depth<= {tools.max_depth} "
              f"and sub_calls< {tools.max_sub_calls} (placeholder caps, Step 4 sets real)")
    else:
        fails.append("recursion guard logic wrong")

    # --- factory convenience
    try:
        t2 = dt.make_tools(str(db))
        if t2.list_chunks("docA"):
            print("[PASS] make_tools() factory opens store + wraps tools")
        else:
            fails.append("make_tools factory broken")
        t2.store.close()
    except ds.DocumentStoreError:
        fails.append("make_tools raised unexpectedly")

    store.close()
    db.unlink(missing_ok=True)
    db.parent.rmdir()

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print(" ", f)
        raise SystemExit(1)
    print("\nALL DOCUMENT_TOOLS STEP-2 CHECKS PASS — four tools + trace seam + guard verified.")


if __name__ == "__main__":
    main()
