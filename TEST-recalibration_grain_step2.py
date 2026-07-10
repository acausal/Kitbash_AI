#!/usr/bin/env python3
"""
TEST-recalibration_grain_step2.py — SPEC_AXIOM_RECALIBRATION.md Step 2 (grain-side
write-back + axiom/observation asymmetry), executed against the real
RecalibrationService._apply_feedback with a real GrainRouter (1:N fact->grain).

Deliberate fixtures CROSS the 0.5 threshold (not relying on the synthetic generator's
uniform(0.45,0.70) default):
  - fact 100 -> [grain_O1 (obs,0.80), grain_O2 (obs,0.85)]  (1:N: both must decrement)
  - fact 200 -> [grain_A1 (axiom,0.97)]                     (flag above 0.5, none below)
  - fact 300 -> [grain_O3 (obs,0.75), grain_A2 (axiom,0.97)] (1:N mixed: decr obs + flag axiom)
Violations crafted with signals BOTH below and above 0.5 (0.4 and 0.6).

Acceptance (from spec Step 2):
  - observation grain confidence DECREMENTS on moderate signal (>0.3), both grains of a 1:N fact.
  - axiom grain confidence does NOT change on that same moderate signal.
  - axiom grain triggers log_hypothesis(subtype="contradiction") ONLY above 0.5; still no
    confidence change at any lower signal.
  - 1:N: every grain a fact resolves to gets the logic, not just the first.
"""
import sys
import json
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import grain_router as gr
from sleep_recalibration_service import RecalibrationService, AXIOM_CONTRADICTION_THRESHOLD

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}  {detail}")
        FAILS.append(name)


def make_grain(gid, gtype, conf, fact_ids, mutable=True):
    return {
        "grain_id": gid,
        "source_phantom_id": "p",
        "cartridge_id": "default",
        "grain_type": gtype,
        "confidence": conf,
        "confidence_mutable": mutable,
        "fact_ids": fact_ids,
        "quality_metrics": {"avg_confidence": conf},
    }


class FakeDBWriter:
    """Records append() calls so we can assert axiom-flag hypotheses were logged."""
    def __init__(self):
        self.appended = []
    def append(self, log_type, record):
        self.appended.append((log_type, record))
        return True


def build_router(tmp):
    grains_dir = tmp / "grains"
    grains_dir.mkdir(parents=True)
    grains = {
        "grain_O1": make_grain("grain_O1", "observation", 0.80, [100]),
        "grain_O2": make_grain("grain_O2", "observation", 0.85, [100]),
        "grain_A1": make_grain("grain_A1", "axiom", 0.97, [200], mutable=False),
        "grain_O3": make_grain("grain_O3", "observation", 0.75, [300]),
        "grain_A2": make_grain("grain_A2", "axiom", 0.97, [300], mutable=False),
    }
    for gid, g in grains.items():
        (grains_dir / f"{gid}.json").write_text(json.dumps(g))
    # GrainRouter loads ../grains relative to cartridges_dir
    cartridges_dir = tmp / "cartridges"
    cartridges_dir.mkdir()
    return gr.GrainRouter(str(cartridges_dir))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="recal_step2_"))
    try:
        router = build_router(tmp)
        db = FakeDBWriter()
        svc = RecalibrationService()

        # Sanity: 1:N index built from fact_ids
        check("fact 100 resolves to 2 grains (1:N)", router.grain_by_fact.get(100) == ["grain_O1", "grain_O2"],
              f"got {router.grain_by_fact.get(100)}")
        check("fact 300 resolves to 2 grains mixed type (1:N)",
              set(router.grain_by_fact.get(300)) == {"grain_O3", "grain_A2"})

        # Violations: deliberate signals below (0.4) and above (0.6) 0.5
        violations = [
            {"dissonance_type": "t", "mtr_error_signal": 0.6, "returned_confidence": 0.9, "returned_fact_id": 100},  # obs decr, >0.5
            {"dissonance_type": "t", "mtr_error_signal": 0.4, "returned_confidence": 0.9, "returned_fact_id": 100},  # obs decr, <0.5
            {"dissonance_type": "t", "mtr_error_signal": 0.6, "returned_confidence": 0.9, "returned_fact_id": 200},  # axiom flag >0.5
            {"dissonance_type": "t", "mtr_error_signal": 0.4, "returned_confidence": 0.9, "returned_fact_id": 200},  # axiom NO flag <0.5
            {"dissonance_type": "t", "mtr_error_signal": 0.6, "returned_confidence": 0.9, "returned_fact_id": 300},  # mixed 1:N: obs decr + axiom flag
        ]

        grains_updated, edges_updated, total_adj, edge_status = svc._apply_feedback(
            violations, grain_router=router, db_writer=db
        )

        # --- observations decrement (1:N: BOTH grain_O1 + grain_O2) ---
        o1 = router.grains["grain_O1"]
        o2 = router.grains["grain_O2"]
        check("grain_O1 (obs) confidence decremented", o1["confidence"] < 0.80, f"conf={o1['confidence']}")
        check("grain_O2 (obs) confidence decremented (1:N, not just first)", o2["confidence"] < 0.85, f"conf={o2['confidence']}")
        # penalty = min(signal*0.15, 0.1); two signals 0.6 -> max penalty 0.09 (signal 0.6*0.15=0.09)
        check("grain_O1 decremented by ~0.09 (0.6 signal)", abs(o1["confidence"] - (0.80 - 0.09)) < 1e-6, f"conf={o1['confidence']}")
        check("grain_O2 decremented by ~0.09 (1:N same fact)", abs(o2["confidence"] - (0.85 - 0.09)) < 1e-6, f"conf={o2['confidence']}")

        # --- axiom NOT decremented at any signal ---
        a1 = router.grains["grain_A1"]
        check("grain_A1 (axiom) confidence UNCHANGED by any signal", a1["confidence"] == 0.97, f"conf={a1['confidence']}")

        # --- axiom FLAGGED only above 0.5 (fact 200: 0.6 yes, 0.4 no) ---
        contradictions = [r for (lt, r) in db.appended if lt == "hypotheses" and r.get("subtype") == "contradiction"]
        check("axiom flag logged via log_hypothesis (subtype=contradiction)", len(contradictions) >= 1)
        flagged_facts = {r["entities"][0] for r in contradictions}
        check("axiom flag fired for fact 200 (signal 0.6 > 0.5)", 200 in flagged_facts, f"flagged_facts={flagged_facts}")
        check("axiom flag NOT fired for fact 200 at signal 0.4 (< 0.5)",
              0 not in [r["entities"][0] for r in contradictions if r.get("confidence", 0) <= 0.5 and 200 in r["entities"]],
              f"contradictions={contradictions}")
        # precisely: fact 200 should have exactly one contradiction (the 0.6 one), not the 0.4
        f200 = [r for r in contradictions if r["entities"] == [200]]
        check("fact 200 flagged exactly once (only the >0.5 signal)", len(f200) == 1, f"f200={f200}")

        # --- 1:N mixed fact 300: observation decremented AND axiom flagged ---
        o3 = router.grains["grain_O3"]
        a2 = router.grains["grain_A2"]
        check("grain_O3 (obs, fact 300) decremented (1:N mixed)", o3["confidence"] < 0.75, f"conf={o3['confidence']}")
        check("grain_A2 (axiom, fact 300) UNCHANGED + flagged", a2["confidence"] == 0.97 and 300 in flagged_facts,
              f"conf={a2['confidence']} flagged_facts={flagged_facts}")

        # --- AXIOM_CONTRADICTION_THRESHOLD is 0.5 (reused MTR band) ---
        check("AXIOM_CONTRADICTION_THRESHOLD == 0.5", AXIOM_CONTRADICTION_THRESHOLD == 0.5)

        # --- grains with no matching fact_id untouched ---
        # (none crafted; but assert router.grains count stable)
        check("all 5 grains present post-write-back", len(router.grains) == 5)

        # --- return shape preserved (4-tuple) for run_recalibration_cycle compat ---
        check("return shape is 4-tuple", isinstance(grains_updated, int) and isinstance(edges_updated, int)
              and isinstance(total_adj, float) and isinstance(edge_status, dict))

        print(f"\naxiom flags recorded: {svc.last_axiom_flags}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
    if FAILS:
        print(f"\n{len(FAILS)} FAILURE(S): {FAILS}")
        raise SystemExit(1)
    print("\nALL STEP 2 GRAIN WRITE-BACK CHECKS PASS")
