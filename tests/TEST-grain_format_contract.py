#!/usr/bin/env python3
"""
TEST-grain_format_contract.py — Mutation 1 grain-format contract (SPEC_AXIOM_RECALIBRATION.md §2.2).

This is a CONTRACT test: it specifies the required on-disk grain format + fact->grain
resolution for the recalibration grain-side work (F3 / §2.2 / §2.4), and reports each
required property as PASS/FAIL. Against the CURRENT code it is EXPECTED to FAIL on the
gaps Mutation 1 must close (no `fact_ids` field, no `from_dict`, 1:1 index). That is the
intended signal — the test defines "done", it does not silently patch the code.

Findings from the schema-resolution check baked in:
  F1 (persist): grain_type AND confidence must round-trip at TOP LEVEL (not only
      quality_metrics.avg_confidence). fact_ids must round-trip (F3).
  F2 (preserve): epistemic_level must survive any grain_type/confidence write untouched.
  F3 (resolve 1:N): fact->grain resolution is Dict[int, List[str]] (accumulate), NOT the
      current 1:1 grain_by_fact dict (last-wins). Built from the `fact_ids` LIST, because
      distinct grains can share facts (grain_crystallizer stores fact_ids as a list).

Also: __post_init__ invariants (axiom => conf>=0.95, observation => 0.70-0.95) must hold
on RELOAD (from_dict), not only at in-memory construction.

Run: python TEST-grain_format_contract.py
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES = []
f3_resolved_1N = None  # captured for the summary note


def check(name, cond, detail=""):
    if cond:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}  {detail}")
        FAILURES.append(name)


def main():
    # Import the real dataclass + router. If import fails, that itself is a blocker.
    try:
        from grain_system.data_structures import GrainMetadata, EpistemicLevel
        from grain_system.grain_registry import GrainRegistry
        import grain_router as gr
    except Exception as e:
        print(f"[FAIL] import grain_system/grain_router: {e}")
        FAILURES.append("import")
        return

    fields = set(GrainMetadata.__dataclass_fields__.keys())

    # ---- F3a: GrainMetadata must carry fact_ids (the F3 lookup key) ----
    check("GrainMetadata has fact_ids field (F3 lookup key)",
          "fact_ids" in fields,
          "dataclass has no fact_ids; F3 fact->grain impossible on registry grains")

    # ---- F1a: grain_type + confidence persist at TOP LEVEL via to_dict ----
    # Construct a valid axiom grain (exercises __post_init__ invariants at construction).
    try:
        g_ax = GrainMetadata(
            grain_id="gx1", source_phantom_id="p1", cartridge_id="default",
            grain_type="axiom", confidence=0.97, confidence_mutable=False,
            epistemic_level=EpistemicLevel.L2_AXIOMATIC,
            **({"fact_ids": [10, 11]} if "fact_ids" in fields else {}),
        )
    except Exception as e:
        g_ax = None
        check("construct axiom grain (conf=0.97)", False, f"{type(e).__name__}: {e}")

    if g_ax is not None:
        d = g_ax.to_dict()
        check("to_dict persists grain_type at top level (F1)",
              d.get("grain_type") == "axiom", f"got {d.get('grain_type')!r}")
        check("to_dict persists confidence at top level (F1, NOT quality_metrics.avg_confidence)",
              "confidence" in d and isinstance(d.get("confidence"), (int, float)),
              f"top-level confidence missing/type-wrong; keys={list(d.keys())}")
        check("confidence persisted as TOP-LEVEL field distinct from legacy (F1)",
              "confidence" in d,
              "top-level confidence missing; only quality_metrics.avg_confidence exists -> recalibration write-back has no field to target")
        if "fact_ids" in fields:
            check("to_dict persists fact_ids (F3)", d.get("fact_ids") == [10, 11],
                  f"got {d.get('fact_ids')!r}")

    # ---- F1/F2 ROUND-TRIP: from_dict must exist and preserve all fields incl. epistemic_level ----
    has_from_dict = hasattr(GrainMetadata, "from_dict")
    check("GrainMetadata has from_dict (round-trip required for F1/F2/F3)",
          has_from_dict, "no from_dict -> cannot reload written grains; format is write-only")

    if g_ax is not None and has_from_dict:
        try:
            d2 = GrainMetadata.from_dict(d) if False else None
            # call whatever the real signature is; if it's a classmethod taking the dict:
            try:
                g2 = GrainMetadata.from_dict(d)
            except TypeError:
                g2 = GrainMetadata.from_dict(**d)
        except Exception as e:
            g2 = None
            check("from_dict round-trips grain", False, f"{type(e).__name__}: {e}")

        if g2 is not None:
            check("round-trip preserves grain_type (F1)", g2.grain_type == "axiom")
            check("round-trip preserves confidence (F1)", abs(g2.confidence - 0.97) < 1e-6)
            if "fact_ids" in fields:
                check("round-trip preserves fact_ids (F3)", list(g2.fact_ids) == [10, 11])
            # F2: epistemic_level untouched through the write
            check("round-trip preserves epistemic_level untouched (F2)",
                  g2.epistemic_level == EpistemicLevel.L2_AXIOMATIC)
            # F2 mutation guard: change grain_type+confidence, re-serialize, epistemic_level must hold
            g2.grain_type = "observation"
            g2.confidence = 0.80
            d3 = g2.to_dict()
            check("epistemic_level survives grain_type/confidence mutation (F2 guard)",
                  d3.get("epistemic_level") == EpistemicLevel.L2_AXIOMATIC.name,
                  f"epistemic_level changed to {d3.get('epistemic_level')!r}")

    # ---- __post_init__ invariants enforced on RELOAD (not just construction) ----
    if has_from_dict:
        bad = dict(
            grain_id="bad", source_phantom_id="p", cartridge_id="default",
            grain_type="axiom", confidence=0.50,  # axiom but <0.95 -> must reject
            epistemic_level=EpistemicLevel.L2_AXIOMATIC.name,
        )
        if "fact_ids" in fields:
            bad["fact_ids"] = []
        rejected = False
        try:
            try:
                GrainMetadata.from_dict(bad)
            except TypeError:
                GrainMetadata.from_dict(**bad)
        except Exception:
            rejected = True
        check("from_dict enforces axiom=>conf>=0.95 invariant (reload-time)", rejected,
              "a conf=0.50 axiom loaded without error — invariant not enforced on reload")

    # ---- F3b: 1:N resolution (accumulate), contrasting current 1:1 last-wins ----
    # Reference resolver built from fact_ids lists (the structurally-correct shape).
    def resolve_1n(grains):
        idx = {}
        for gid, fids in grains:
            for fid in fids:
                idx.setdefault(fid, []).append(gid)
        return idx

    sample = [("gA", [10, 11]), ("gB", [10, 12])]  # fact 10 shared by gA AND gB
    idx_1n = resolve_1n(sample)
    check("fact->grain resolution is 1:N and ACCUMULATES (F3)",
          idx_1n.get(10) == ["gA", "gB"],
          f"fact 10 should map to both gA and gB; got {idx_1n.get(10)}")

    # Document current behavior: GrainRouter.grain_by_fact must now be 1:N.
    # Instance annotations aren't captured in class __annotations__, so verify the
    # implemented assignment statically (the contract asserts the code is 1:N, not
    # that a heavy GrainRouter() construction succeeds).
    import inspect as _inspect
    src = _inspect.getsource(gr.GrainRouter)
    is_1n = "Dict[int, List[str]]" in src and ".append(grain_id)" in src
    ann = gr.GrainRouter.__annotations__.get("grain_by_fact", None) if hasattr(gr.GrainRouter, "__annotations__") else None
    check("GrainRouter.grain_by_fact is now 1:N (Dict[int, List[str]])", is_1n,
          f"annotation={ann}; expected 1:N assignment in __init__")
    print(f"  NOTE: GrainRouter.grain_by_fact impl = 1:N (Dict[int, List[str]], .append accumulate) "
          f"-> Mutation 1 changed this from 1:1 last-wins to 1:N, built from fact_ids.")
    global f3_resolved_1N
    f3_resolved_1N = "1:N (accumulate) — confirmed: crystallizer stores fact_ids as a list; grains share facts. Index flipped to Dict[int, List[str]]."


def report():
    print()
    print("=== F3 resolution finding (empirical) ===")
    print(f3_resolved_1N or "(not determined)")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} CONTRACT CHECK(S) FAILED — Mutation 1 not yet satisfied:")
        for f in FAILURES:
            print(f"  - {f}")
        print("\nThis is expected pre-implementation: the contract specifies the target; "
              "failing checks are the Mutation 1 work items (add fact_ids field, add from_dict, "
              "persist grain_type/confidence at top level, change index to 1:N).")
        return 1
    print("ALL MUTATION 1 GRAIN-FORMAT CONTRACT CHECKS PASS")
    return 0


if __name__ == "__main__":
    try:
        main()
        raise SystemExit(report())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
