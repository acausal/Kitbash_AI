"""MTR v6.1 profiling + contract checks (core measurement tooling).

Measures real latency of the production MTR-Ebbinghaus engine (KitbashMTREngine
from MTR_v6_1.py) on this hardware, and asserts explicit latency/shape contracts.

This is "verification, not new functionality" (roadmap Priority 0 / Phase B item):
it characterizes the shipping MTR engine so latency contracts can be written from
real data. It does NOT modify MTR.

Design notes (grounded in repo audit, 2026-07-15):
- Production config (query_orchestrator_factory.create_query_orchestrator):
  vocab_size=50257, d_model=256, d_state=144. NOTE: MTR_v6_1.KitbashMTREngine's
  *default* d_state=128 is NOT a perfect square -> would crash the d_state
  assertion. The factory overrides to 144 (12^2). We use 144 to match prod.
- Latency bounds below are EXPLICIT PLACEHOLDERS, not validated targets. Run this
  once to learn real numbers, then tighten. The measured values are always
  printed so contracts can be set from evidence.
- If torch is unavailable or construction fails, the script reports the blocker
  and exits non-zero. It never fakes green.
- v6.1 has known design debt (see POSTMORTEM_MTR_v6.md: layer-name drift, invented
  clusters). We measure + contract-check the engine as-is; we do not validate it
  against the (unreliable) v6 spec.

Usage:
    python mtr_profiler.py [--runs 20] [--seq-len 20] [--output-json out.json]
"""
from __future__ import annotations

import sys
import time
import json
import argparse
from typing import Dict, Any, List, Optional


# Minimal CLI glue (no historical_common dependency so this runs from repo root
# standalone, like other core modules). Keeps the module dependency-free at the
# CLI layer; the only third-party dep is torch (required by MTR_v6_1 itself).
def _base_argparse(tool: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=tool)
    p.add_argument("--input", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--verbose", action="store_true")
    return p


def _write_output(result: dict, path: Optional[str]) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")


# Explicit placeholder latency bounds (ms). Tighten after first real run.
CONTRACT_INIT_MS_MAX = 20000.0        # engine construction (allocates 50257x256 embed)
CONTRACT_FORWARD_MS_MAX = 5000.0      # single forward() call, (1, seq_len)
CONTRACT_SNAPSHOT_MS_MAX = 5000.0     # single get_epistemic_snapshot() call

PROD_CONFIG = {"vocab_size": 50257, "d_model": 256, "d_state": 144}


def _pct(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def run_profiling(runs: int, seq_len: int, device: str = "cpu") -> Dict[str, Any]:
    """Construct the real engine and measure latency. Returns a result dict."""
    try:
        import torch
    except Exception as e:
        return {"ok": False, "blocker": f"torch unavailable: {e}"}

    try:
        from MTR_v6_1 import KitbashMTREngine, LAYER_NAMES, DissonanceSensor
    except Exception as e:
        return {"ok": False, "blocker": f"MTR_v6_1 import failed: {e}"}

    # --- Contract 1: construction latency ---
    t0 = time.perf_counter()
    try:
        torch.manual_seed(42)
        engine = KitbashMTREngine(
            vocab_size=PROD_CONFIG["vocab_size"],
            d_model=PROD_CONFIG["d_model"],
            d_state=PROD_CONFIG["d_state"],
        )
        engine = engine.to(device)
    except Exception as e:
        return {"ok": False, "blocker": f"engine construction failed: {e}"}
    init_ms = (time.perf_counter() - t0) * 1000

    sensor = DissonanceSensor()
    token_ids = torch.randint(0, PROD_CONFIG["vocab_size"], (1, seq_len))

    forward_ms: List[float] = []
    snapshot_ms: List[float] = []
    last_state = None
    last_error_mean = None
    snapshot_keys_ok = False
    dissonance_ok = False

    for _ in range(runs):
        # --- Contract 2: forward() latency + shape ---
        t0 = time.perf_counter()
        logits, error_signal, state = engine(token_ids, state=last_state, kappa=1.0)
        forward_ms.append((time.perf_counter() - t0) * 1000)
        last_state = state
        last_error_mean = float(error_signal.mean().item())
        # shape contract: logits (1, seq_len, vocab_size)
        if tuple(logits.shape) != (1, seq_len, PROD_CONFIG["vocab_size"]):
            return {"ok": False, "blocker": f"unexpected logits shape {tuple(logits.shape)}"}

        # --- Contract 3: get_epistemic_snapshot latency + keys ---
        t0 = time.perf_counter()
        snap = engine.get_epistemic_snapshot(token_ids, state=last_state, kappa=1.0)
        snapshot_ms.append((time.perf_counter() - t0) * 1000)
        if set(snap.keys()) == set(LAYER_NAMES):
            snapshot_keys_ok = True
        # DissonanceSensor must not KeyError (v6 regression guard)
        dis = sensor(error_signal, snap)
        if "dissonance_active" in dis:
            dissonance_ok = True

    # --- Contract evaluation ---
    fwd_p50 = _pct(forward_ms, 50)
    fwd_p95 = _pct(forward_ms, 95)
    snap_p50 = _pct(snapshot_ms, 50)

    contracts = [
        {"name": "init_latency", "measured_ms": round(init_ms, 2),
         "max_ms": CONTRACT_INIT_MS_MAX, "pass": init_ms <= CONTRACT_INIT_MS_MAX},
        {"name": "forward_latency_p95", "measured_ms": round(fwd_p95, 2),
         "max_ms": CONTRACT_FORWARD_MS_MAX, "pass": fwd_p95 <= CONTRACT_FORWARD_MS_MAX},
        {"name": "snapshot_latency_p50", "measured_ms": round(snap_p50, 2),
         "max_ms": CONTRACT_SNAPSHOT_MS_MAX, "pass": snap_p50 <= CONTRACT_SNAPSHOT_MS_MAX},
        {"name": "snapshot_keys_match_LAYER_NAMES", "measured_ms": None,
         "max_ms": None, "pass": snapshot_keys_ok},
        {"name": "dissonance_sensor_no_keyerror", "measured_ms": None,
         "max_ms": None, "pass": dissonance_ok},
    ]
    all_pass = all(c["pass"] for c in contracts)

    return {
        "ok": True,
        "config": PROD_CONFIG,
        "device": device,
        "runs": runs,
        "seq_len": seq_len,
        "init_ms": round(init_ms, 2),
        "forward_ms": {
            "min": round(min(forward_ms), 2), "p50": round(fwd_p50, 2),
            "p95": round(fwd_p95, 2), "max": round(max(forward_ms), 2),
        },
        "snapshot_ms": {"p50": round(snap_p50, 2), "max": round(max(snapshot_ms), 2)},
        "last_error_signal_mean": round(last_error_mean, 6) if last_error_mean is not None else None,
        "state_time_after_runs": int(last_state["time"]) if last_state else None,
        "contracts": contracts,
        "all_contracts_pass": all_pass,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = _base_argparse("mtr_profiler")
    ap.description = "Profile MTR v6.1 engine latency + check explicit contracts (measurement, not new functionality)."
    ap.add_argument("--runs", type=int, default=20, help="Number of forward/snapshot iterations")
    ap.add_argument("--seq-len", type=int, default=20, help="Token sequence length per call")
    ap.add_argument("--device", default="cpu", help="torch device")
    ap.add_argument("--output-json", dest="output", help="Write result JSON to this path (or stdout)")
    args = ap.parse_args(list(argv) if argv is not None else None)

    result = run_profiling(args.runs, args.seq_len, args.device)

    if not result.get("ok"):
        # Honest blocker report (never fake green).
        payload = {"ok": False, "blocker": result.get("blocker", "unknown"),
                   "note": "MTR profiling could not run; see blocker."}
        _write_output(payload, args.output)
        sys.stderr.write(f"MTR_PROFILER BLOCKED: {payload['blocker']}\n")
        return 2

    # Print a human-readable summary to stderr (chat channel = payload only).
    sys.stderr.write(
        f"MTR v6.1 profile: init={result['init_ms']}ms  "
        f"forward p50={result['forward_ms']['p50']}ms p95={result['forward_ms']['p95']}ms  "
        f"snapshot p50={result['snapshot_ms']['p50']}ms  "
        f"contracts={'PASS' if result['all_contracts_pass'] else 'FAIL'}\n"
    )
    _write_output(result, args.output)
    return 0 if result["all_contracts_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
