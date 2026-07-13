"""TEST-signal_transforms.py — SPEC_BOUNDED_SIGNAL_CONSUMPTION.

Asserts: clamp bounds; gate equivalence (default behavior identical today);
penalty equivalence at the gate; negative-raw penalty -> 0 (the only delta).
Read-only; no live data touched.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from signal_transforms import bounded_error, gate_trips, GATE_THRESHOLD

# Shared penalty constants (mirrors sleep_recalibration_service.EDGE_PENALTY_*)
RATE = 0.15
CAP = 0.1

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


# 1) clamp bounds
check("clamp 8.77 -> 1.0", bounded_error(8.77) == 1.0, str(bounded_error(8.77)))
check("clamp -7.77 -> 0.0", bounded_error(-7.77) == 0.0, str(bounded_error(-7.77)))
check("clamp 0.5 -> 0.5 (identity in range)",
      bounded_error(0.5) == 0.5, str(bounded_error(0.5)))
check("clamp 0.0 -> 0.0", bounded_error(0.0) == 0.0, str(bounded_error(0.0)))

# 2) gate equivalence at 0.45 / 0.5 / 0.51 / 8.77
#    clamp(x) > 0.5  <=>  x > 0.5  for all x >= 0
check("gate 0.45 -> False", gate_trips(0.45) is False, str(gate_trips(0.45)))
check("gate 0.5 -> False (strict >, identical to today)",
      gate_trips(0.5) is False, str(gate_trips(0.5)))
check("gate 0.51 -> True", gate_trips(0.51) is True, str(gate_trips(0.51)))
check("gate 8.77 -> True", gate_trips(8.77) is True, str(gate_trips(8.77)))
check("gate -7.77 -> False", gate_trips(-7.77) is False, str(gate_trips(-7.77)))

# 3) penalty equivalence at raw 0.6 and raw 3.0
#    min(clamp(x)*RATE, CAP) == min(x*RATE, CAP) for every x that trips the gate
p06_new = min(bounded_error(0.6) * RATE, CAP)
p06_old = min(0.6 * RATE, CAP)
check("penalty equiv raw 0.6", p06_new == p06_old, f"new={p06_new} old={p06_old}")
p30_new = min(bounded_error(3.0) * RATE, CAP)
p30_old = min(3.0 * RATE, CAP)
check("penalty equiv raw 3.0", p30_new == p30_old, f"new={p30_new} old={p30_old}")
# below the gate (0.45) the formal equivalence still holds (clamp is identity < 1.0)
p45_new = min(bounded_error(0.45) * RATE, CAP)
p45_old = min(0.45 * RATE, CAP)
check("penalty equiv raw 0.45", p45_new == p45_old, f"new={p45_new} old={p45_old}")

# 4) negative-raw penalty is 0 (the ONLY behavioral delta: no negative reward)
p_neg = min(bounded_error(-7.77) * RATE, CAP)
check("negative-raw penalty == 0", p_neg == 0.0, f"penalty={p_neg}")

# 5) GATE_THRESHOLD unchanged from historical default
check("GATE_THRESHOLD == 0.5", GATE_THRESHOLD == 0.5, str(GATE_THRESHOLD))


if __name__ == "__main__":
    failed = [r for r in results if not r[1]]
    print()
    if failed:
        print(f"SIGNAL TRANSFORMS: {len(results)-len(failed)}/{len(results)} PASS")
        raise SystemExit(1)
    print(f"SIGNAL TRANSFORMS: {len(results)}/{len(results)} PASS")
