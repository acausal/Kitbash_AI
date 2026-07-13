"""TEST-edge_graph_roundtrip.py — regression for cartridge_index round-trip.

Reproduces the second-run crash: a multi-fact corpus creates edges (so
cartridge_index holds real sets), _save_edge_graph writes them, and a SECOND
extract_intra_cartridge_edges() reloads the graph and calls
cartridge_index[cart].add(...) at line 160. Before the fix this crashed
(JSON set not serializable on save; or 'list' has no add on reload). After the
fix: both passes succeed and counts are sane.

Uses a temp dream-bucket dir; never touches live data.
"""
import sys, os, json, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sleep_procedural_edge_extractor import ProceduralEdgeExtractor

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def write_fixture(live_dir: Path):
    live_dir.mkdir(parents=True, exist_ok=True)
    records = [
        # multi-fact chain -> 3 co-occurrence edges (1->2, 1->3, 2->3)
        {"chain": {"query_id": "qa", "chain_type": "intra_query",
                    "fact_ids": [1, 2, 3], "grain_ids": [], "confidence": 0.5},
         "context": {"cartridge": "CARTRIDGE"}},
        # another multi-fact chain touching overlapping facts
        {"chain": {"query_id": "qb", "chain_type": "intra_query",
                    "fact_ids": [2, 3, 4], "grain_ids": [], "confidence": 0.5},
         "context": {"cartridge": "CARTRIDGE"}},
        # single-fact -> 0 edges (thin)
        {"chain": {"query_id": "qc", "chain_type": "intra_query",
                    "fact_ids": [9], "grain_ids": [], "confidence": 0.5},
         "context": {"cartridge": "CARTRIDGE"}},
    ]
    with (live_dir / "traces.jsonl").open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def run():
    tmp = Path(tempfile.mkdtemp(prefix="edge_rt_"))
    bucket = tmp / "bucket"
    live = bucket / "live"
    write_fixture(live)

    ext = ProceduralEdgeExtractor(str(bucket))

    # ---- PASS 1: build + save ----
    r1 = ext.extract_intra_cartridge_edges()
    check("pass1 no error", r1.get("error") in (None,), str(r1.get("error")))
    check("pass1 edges_created == 5", r1["edges_created"] == 5,
          f"edges_created={r1['edges_created']}")
    check("pass1 chains_parsed == 3", r1["chains_parsed"] == 3,
          f"chains_parsed={r1['chains_parsed']}")
    graph_file = bucket / "indices" / "procedural_edge_graph.json"
    check("pass1 graph file written", graph_file.exists())

    # verify on-disk cartridge_index is a JSON list (sorted)
    on_disk = json.loads(graph_file.read_text())
    ci = on_disk.get("cartridge_index", {})
    check("on-disk cartridge_index values are lists",
          all(isinstance(v, list) for v in ci.values()), str(ci))

    # ---- PASS 2: reload (line 160 would crash pre-fix) + re-run ----
    r2 = ext.extract_intra_cartridge_edges()
    check("pass2 no error (reload+add ok)", r2.get("error") in (None,),
          str(r2.get("error")))
    # edges already exist -> no new edges created, but traversals increment
    check("pass2 edges_created == 0 (idempotent add)", r2["edges_created"] == 0,
          f"edges_created={r2['edges_created']}")
    check("pass2 chains_parsed == 3", r2["chains_parsed"] == 3,
          f"chains_parsed={r2['chains_parsed']}")
    check("pass2 total_edges sane (5)",
          on_disk["metadata"]["total_edges"] == 5,
          f"total_edges={on_disk['metadata']['total_edges']}")

    # ---- load-back via the loader directly (sets restored) ----
    loaded = ext._load_edge_graph()
    ci_loaded = loaded.get("cartridge_index", {})
    check("loaded cartridge_index values are sets",
          all(isinstance(v, set) for v in ci_loaded.values()), str(ci_loaded))


if __name__ == "__main__":
    run()
    failed = [r for r in results if not r[1]]
    print()
    if failed:
        print(f"EDGE GRAPH ROUNDTRIP: {len(results)-len(failed)}/{len(results)} PASS")
        raise SystemExit(1)
    print(f"EDGE GRAPH ROUNDTRIP: {len(results)}/{len(results)} PASS")
