"""TEST-trace_chain_contract.py — SPEC_TRACE_CHAIN_CONTRACT Phase 1 (RED->GREEN).

Asserts the canonical chain shape, round-trip, and ORDER-INDEPENDENT pairwise
co-occurrence edge semantics. No runtime behavior changed; this pins the
contract both writer and extractor will import.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from interfaces.trace_chain import TraceChain, iter_cooccurrence_edges

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


# 1) to_dict equals the exact on-disk dict shape
tc = TraceChain(
    query_id="76844644-957b-4745-9011-0b39f041f3e9",
    chain_type="intra_query",
    fact_ids=[1],
    grain_ids=[],
    confidence=-8.618160247802734,
)
expected = {
    "query_id": "76844644-957b-4745-9011-0b39f041f3e9",
    "chain_type": "intra_query",
    "fact_ids": [1],
    "grain_ids": [],
    "confidence": -8.618160247802734,
}
check("1 to_dict matches on-disk shape", tc.to_dict() == expected,
      str(tc.to_dict()))


# 2) from_dict round-trips; raises on missing required fields
rt = TraceChain.from_dict(expected)
check("2a from_dict round-trips", rt == tc, str(rt))
bad_missing = False
try:
    TraceChain.from_dict({"fact_ids": [1]})  # no query_id
except ValueError:
    bad_missing = True
check("2b from_dict raises on missing query_id", bad_missing)
bad_missing_facts = False
try:
    TraceChain.from_dict({"query_id": "q1"})  # no fact_ids
except ValueError:
    bad_missing_facts = True
check("2c from_dict raises on missing fact_ids", bad_missing_facts)


# 3) [1,3,9] -> 3 edges (1->3, 1->9, 3->9), all a<b
edges = list(iter_cooccurrence_edges(TraceChain(query_id="q", fact_ids=[1, 3, 9]), "CARTRIDGE"))
want = {(1, 3), (1, 9), (3, 9)}
check("3 [1,3,9] yields 3 co-occurrence edges", set(edges) == want and len(edges) == 3,
      f"got {edges}")


# 4) [1] -> 0 edges (thin corpus correct)
single = list(iter_cooccurrence_edges(TraceChain(query_id="q", fact_ids=[1]), "CARTRIDGE"))
check("4 [1] yields 0 edges (thin corpus)", single == [], str(single))


# 5) order-independent: [9,1,3] == [1,3,9]
a = set(iter_cooccurrence_edges(TraceChain(query_id="q", fact_ids=[9, 1, 3]), "X"))
b = set(iter_cooccurrence_edges(TraceChain(query_id="q", fact_ids=[1, 3, 9]), "X"))
check("5 order-independent (set-sourced fact_ids)", a == b == {(1, 3), (1, 9), (3, 9)},
      f"a={a} b={b}")


# 6) malformed record (obsolete list-shaped chain) is REJECTED by the contract,
#    so the extractor counts it as a skip rather than crashing or misparsing.
bad_list_shape = False
try:
    TraceChain.from_dict([1, 2, 3])  # the old list-of-steps shape -> must raise
except (ValueError, TypeError):
    bad_list_shape = True
check("6 malformed list-shaped chain rejected (counted as skip)", bad_list_shape)


failed = [r for r in results if not r[1]]
print()
if failed:
    print(f"TRACE CHAIN CONTRACT: {len(results)-len(failed)}/{len(results)} PASS")
    raise SystemExit(1)
print(f"TRACE CHAIN CONTRACT: {len(results)}/{len(results)} PASS")
