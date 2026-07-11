#!/usr/bin/env python3
"""
DIAGNOSTIC-trace_signal_check.py — READ-ONLY diagnostic pass (SPEC: Trace Signal
Validation, 2026-07-11).

Answers three data questions about the ACTUAL on-disk dream-bucket trace data:
  Q1: negative confidence / mtr_error_signal values — bug or harness artifact?
  Q2: does grain_ids ever get populated on real trace records?
  Q3: real end-to-end sleep run, or fixture/synthetic data?

STRICTLY READ-ONLY: opens files read-only, never writes/mutates/deletes anything.
Skips and counts malformed JSON lines instead of crashing.

Run: python DIAGNOSTIC-trace_signal_check.py [--dir PATH_TO/dream_bucket/live]
Default dir resolves next to this script's repo (Candidate B live dir).
"""
import argparse
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

REPO_LIVE = Path(__file__).resolve().parent / "data" / "subconscious" / "dream_bucket" / "live"


def load_jsonl(path: Path):
    """Yield parsed dicts; collect malformed lines separately. Read-only."""
    good, bad = [], []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    good.append(json.loads(line))
                except json.JSONDecodeError:
                    bad.append((ln, line[:120]))
    except FileNotFoundError:
        return [], bad, True
    return good, bad, False


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt(v, n=4):
    return round(v, n)


# ---------------------------------------------------------------------------
# Q1 — Confidence sign audit
# ---------------------------------------------------------------------------
def q1_sign_audit(records_by_file):
    print("\n" + "=" * 70)
    print("Q1 — CONFIDENCE SIGN AUDIT (negative values: bug vs artifact?)")
    print("=" * 70)

    fields_of_interest = ["confidence", "mtr_error_signal", "returned_confidence"]
    # collect all numeric values per (file, field)
    by_file_field = defaultdict(list)
    neg_examples = []
    clustering = defaultdict(lambda: Counter())  # (file, field) -> attr -> Counter

    for fname, recs in records_by_file.items():
        for rec in recs:
            # top-level
            for f in fields_of_interest:
                if f in rec and rec[f] is not None:
                    v = num(rec[f])
                    if v is None:
                        continue
                    by_file_field[(fname, f)].append(v)
                    if v < 0:
                        # cluster by session_id / chain_type / dissonance_type / timestamp
                        sess = rec.get("session_id", rec.get("chain", {}).get("session_id", "NONE"))
                        ctype = rec.get("chain", {}).get("chain_type", rec.get("chain_type", "NONE"))
                        dtype = rec.get("dissonance_type", "NONE")
                        ts = rec.get("timestamp", "NONE")
                        clustering[(fname, f)]["session_id:" + str(sess)] += 1
                        clustering[(fname, f)]["chain_type:" + str(ctype)] += 1
                        clustering[(fname, f)]["dissonance_type:" + str(dtype)] += 1
                        if len(neg_examples) < 8:
                            neg_examples.append({
                                "file": fname, "field": f, "value": v,
                                "session_id": sess, "chain_type": ctype,
                                "dissonance_type": dtype, "timestamp": ts,
                                "sample": rec,
                            })

    any_neg = False
    for (fname, f), vals in sorted(by_file_field.items()):
        if not vals:
            continue
        n_neg = sum(1 for x in vals if x < 0)
        n_pos = sum(1 for x in vals if x > 0)
        n_zero = sum(1 for x in vals if x == 0)
        n_neg_here = n_neg
        if n_neg_here > 0:
            any_neg = True
        print(f"\n  [{fname}] field='{f}': n={len(vals)} "
              f"neg={n_neg} pos={n_pos} zero={n_zero} "
              f"min={fmt(min(vals))} max={fmt(max(vals))} "
              f"mean={fmt(sum(vals)/len(vals))}")
        if n_neg_here > 0:
            cl = clustering[(fname, f)]
            print(f"    NEGATIVE clustering (strongest signal of artifact vs systemic):")
            for k, c in cl.most_common(10):
                print(f"      {k}: {c}")

    if not any_neg:
        print("\n  -> No negative confidence/error values found in any file.")
    else:
        print("\n  NEGATIVE-VALUE EXAMPLE RECORDS (full):")
        for ex in neg_examples:
            print(f"    file={ex['file']} field={ex['field']} value={ex['value']} "
                  f"session={ex['session_id']} chain_type={ex['chain_type']} "
                  f"dissonance={ex['dissonance_type']} ts={ex['timestamp']}")
            print(f"      full_record={json.dumps(ex['sample'])[:400]}")

    return any_neg


# ---------------------------------------------------------------------------
# Q2 — grain_ids population rate
# ---------------------------------------------------------------------------
def q2_grain_ids(records_by_file):
    print("\n" + "=" * 70)
    print("Q2 — grain_ids POPULATION RATE (real data vs fixture-only?)")
    print("=" * 70)

    # traces carry chain.grain_ids; also check a top-level grain_ids if any
    total = 0
    nonempty = 0
    empty = 0
    missing = 0
    by_type = defaultdict(lambda: [0, 0, 0])  # chain_type -> [nonempty, empty, missing]

    for fname, recs in records_by_file.items():
        for rec in recs:
            # trace records have nested chain; other records may not
            chain = rec.get("chain")
            if chain is not None and isinstance(chain, dict) and "grain_ids" in chain:
                gids = chain.get("grain_ids", [])
                ctype = chain.get("chain_type", "NONE")
            elif "grain_ids" in rec:
                gids = rec.get("grain_ids", [])
                ctype = rec.get("chain_type", "NONE")
            else:
                gids = None
                ctype = rec.get("chain_type", "NONE")

            total += 1
            if gids is None:
                missing += 1
                by_type[ctype][2] += 1
            elif len(gids) > 0:
                nonempty += 1
                by_type[ctype][0] += 1
            else:
                empty += 1
                by_type[ctype][1] += 1

    print(f"  Records examined: {total}")
    print(f"  grain_ids NON-EMPTY: {nonempty} ({fmt(100*nonempty/max(total,1),2)}%)")
    print(f"  grain_ids EMPTY (present, []): {empty} ({fmt(100*empty/max(total,1),2)}%)")
    print(f"  grain_ids MISSING entirely: {missing} ({fmt(100*missing/max(total,1),2)}%)")
    print("\n  Breakdown by chain_type / record-type:")
    for ctype, (ne, e, m) in sorted(by_type.items()):
        print(f"    {ctype}: nonempty={ne} empty={e} missing={m}")
    return nonempty, empty, missing


# ---------------------------------------------------------------------------
# Q3 — real run vs fixture
# ---------------------------------------------------------------------------
def q3_real_vs_fixture(records_by_file):
    print("\n" + "=" * 70)
    print("Q3 — REAL RUN vs FIXTURE (is the pipeline verified to have run?)")
    print("=" * 70)

    all_ts = []
    session_ids = Counter()
    query_ids = []
    fact_ids_all = []
    sample_feb27 = []

    for fname, recs in records_by_file.items():
        for rec in recs:
            ts = rec.get("timestamp")
            if ts:
                all_ts.append(ts)
            sid = rec.get("session_id")
            if sid:
                session_ids[sid] += 1
            qid = rec.get("query_id")
            if qid:
                query_ids.append(qid)
            chain = rec.get("chain", {})
            fids = chain.get("fact_ids") if isinstance(chain, dict) else None
            if fids:
                fact_ids_all.extend(fids)
            if ts and ts.startswith("2026-02-27"):
                if len(sample_feb27) < 5:
                    sample_feb27.append((fname, rec))

    if all_ts:
        all_ts_sorted = sorted(all_ts)
        print(f"  Timestamp range: {all_ts_sorted[0]}  ->  {all_ts_sorted[-1]}  (n={len(all_ts)})")
    else:
        print("  No timestamps found.")

    print(f"  Distinct session_id values: {len(session_ids)}")
    for s, c in session_ids.most_common(15):
        print(f"    {s}: {c}")
    print(f"  Distinct query_id values: {len(set(query_ids))} (total {len(query_ids)})")
    print(f"  Distinct fact_ids referenced: {len(set(fact_ids_all))} (total refs {len(fact_ids_all)})")

    # fixture tell: sequential/round counts, identical timestamps, single session
    print("\n  FIXTURE/REAL tells:")
    print(f"    only one session_id? {len(session_ids) == 1}  (1 session = strong fixture tell)")
    if fact_ids_all:
        print(f"    fact_id span: min={min(fact_ids_all)} max={max(fact_ids_all)} "
              f"(tight sequential range = possible fixture)")
    print(f"    Feb-27 records found: {len(sample_feb27)} (the 'historical' batch)")
    for fname, rec in sample_feb27:
        print(f"    [{fname}] {json.dumps(rec)[:300]}")

    return all_ts, session_ids, sample_feb27


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(REPO_LIVE),
                    help="Path to dream_bucket/live directory (default: repo Candidate B live dir)")
    args = ap.parse_args()
    live = Path(args.dir)
    if not live.exists():
        print(f"ERROR: live dir not found: {live}")
        sys.exit(2)

    print(f"DIAGNOSTIC trace-signal check — READ-ONLY")
    print(f"Target live dir: {live}")
    print(f"Path real? (exists): {live.exists()}")

    jsonl_files = sorted(live.glob("*.jsonl"))
    print(f"Files found: {[f.name for f in jsonl_files]}")

    records_by_file = {}
    malformed_total = 0
    for f in jsonl_files:
        recs, bad, missing = load_jsonl(f)
        if missing:
            print(f"  [MISSING] {f.name} not readable")
            continue
        records_by_file[f.name] = recs
        malformed_total += len(bad)
        print(f"  {f.name}: {len(recs)} records, {len(bad)} malformed lines skipped")
        for ln, snippet in bad[:3]:
            print(f"      malformed line {ln}: {snippet}")

    print(f"\nTOTAL malformed lines skipped across all files: {malformed_total}")

    any_neg = q1_sign_audit(records_by_file)
    q2_grain_ids(records_by_file)
    q3_real_vs_fixture(records_by_file)

    print("\n" + "=" * 70)
    print("STEP 2 COMPLETE — raw findings above. Step 3 (interpret) is for the")
    print("implementing model to state, NOT auto-concluded here.")
    print("=" * 70)


if __name__ == "__main__":
    main()
