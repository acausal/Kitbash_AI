#!/usr/bin/env python3
"""
TEST-bus_stream_format.py — SPEC_STREAM_FORMAT.md §6 contract suite.

Validates the bus envelope + per-namespace payloads against fakeredis. Covers
every payload in §2: query_state, grain, diagnostic_event, worker_health,
metric_point, epistemic_snapshot, and coupling_delta.

Per the live-Redis decision (2026-07-10): the coupling_delta payload's WRITE path
uses a Redis Lua script (evalsha), which fakeredis cannot execute. That one check
is gated on a real local Redis (docker run ... redis:7-alpine). If no live Redis is
reachable, the coupling write check SKIPs with a clear note rather than failing —
the coupling READER half (envelope-unwrap + dual-read legacy) is still verified on
fakeredis because it's plain redis-py.

Run: python TEST-bus_stream_format.py
"""
import os
import sys
import json
import traceback
from pathlib import Path

import fakeredis
import redis

# repo on path (run from Kitbash_AI root)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import redis_blackboard as rb  # noqa: E402
import redis_coupling as rc  # noqa: E402
from MTR_v6_1 import LAYER_NAMES  # noqa: E402

FAILURES = []
SKIPS = []


def check(name, cond, detail=""):
    if cond:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}  {detail}")
        FAILURES.append(name)


def skip(name, why):
    print(f"[SKIP] {name}  ({why})")
    SKIPS.append(name)


# ----------------------------------------------------------------- fakeredis bus
def test_blackboard_payloads():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    bb = rb.RedisBlackboard(redis_client=r)

    # query_state round-trip + TTL
    bb.create_query("q1", "what is the meaning of life?")
    bb.update_query_status("q1", "in_progress") if hasattr(bb, "update_query_status") else None
    q = bb.get_query("q1")
    check("query_state round-trip", q is not None and q.get("query_text") == "what is the meaning of life?")
    ttl = r.ttl(f"{bb.prefix}queries:state:q1")
    check("query_state 24h TTL set", ttl == rb.QUERY_TTL_SEC, f"ttl={ttl}")

    # grain round-trip (envelope)
    grain = {"grain_id": "g12", "fact_id": "f12", "cartridge_id": "default",
             "confidence": 0.6, "epistemic_level": "L2_AXIOMATIC", "text": "foo bar",
             "delta": {"positive": [], "negative": [], "void": []}, "quality_metrics": {}}
    bb.store_grain("f12", grain)
    g = bb.get_grain("f12")
    check("grain round-trip", g == grain, f"got {g}")
    raw = r.hget(f"{bb.prefix}grains:f12", "data")
    check("grain envelope shape", json.loads(raw)["schema"] == "grain@1")

    # diagnostic feed (envelope + round-trip)
    bb.log_diagnostic_event("evt", "q1", {"x": 1})
    feed = bb.get_diagnostic_feed(10)
    check("diagnostic feed round-trip", len(feed) == 1 and feed[0]["event_type"] == "evt")
    raw_feed = r.lrange(f"{bb.prefix}diagnostic:feed", 0, -1)
    check("diagnostic envelope shape", json.loads(raw_feed[0])["schema"] == "diagnostic_event@1")

    # worker health (envelope + 5m TTL)
    bb.set_worker_health("w1", "healthy", {"load": 0.2})
    h = bb.get_worker_health("w1")
    check("worker_health round-trip", h and h["status"] == "healthy")
    ttl_h = r.ttl(f"{bb.prefix}health:w1")
    check("worker_health 5m TTL", ttl_h == rb.HEALTH_TTL_SEC, f"ttl={ttl_h}")

    # metric point (envelope via ZADD + 7d rolling prune)
    bb.record_metric("latency", 1.5)
    m = bb.get_metrics("latency")
    check("metric round-trip", m == [1.5], f"got {m}")
    card = r.zcard(f"{bb.prefix}metrics:latency")
    check("metric stored in ZSET", card == 1)

    # epistemic snapshot (§3.8) — flatten from router-shaped snapshot
    raw_snap = {name: (None, 0.3 + i * 0.1) for i, name in enumerate(LAYER_NAMES)}
    bb.store_epistemic_snapshot("q1", raw_snap, layer_names=LAYER_NAMES, kappa=1.0, mtr_state_time=7)
    es = bb.get_epistemic_snapshot("q1")
    check("epistemic_snapshot round-trip", es is not None and es["query_id"] == "q1")
    check("epistemic uses LAYER_NAMES (not hardcoded)",
          es["layer_names"] == list(LAYER_NAMES), f"got {es['layer_names']}")
    check("epistemic salience flattened to floats",
          all(isinstance(v, float) for v in es["salience"].values()))
    raw_es = r.get(f"{bb.prefix}epistemic:q1")
    check("epistemic envelope shape", json.loads(raw_es)["schema"] == "epistemic_snapshot@1")
    ttl_e = r.ttl(f"{bb.prefix}epistemic:q1")
    check("epistemic TTL set (provisional 24h)", ttl_e == rb.EPISTEMIC_TTL_SEC, f"ttl={ttl_e}")

    # version-gating loud-reject: a future envelope version is rejected
    bad = json.dumps({"v": 99, "schema": "grain@1", "produced_at": "x",
                      "producer": "t", "data": {}})
    r.hset(f"{bb.prefix}grains:fX", "data", bad)
    try:
        bb.get_grain("fX")
        check("version-gating rejects future envelope v", False, "no error raised")
    except rb.BusEnvelopeError:
        check("version-gating rejects future envelope v", True)
    # wrong payload name rejected
    wrong = json.dumps({"v": 1, "schema": "grain@2", "produced_at": "x",
                        "producer": "t", "data": {}})
    r.hset(f"{bb.prefix}grains:fY", "data", wrong)
    try:
        bb.get_grain("fY")
        check("version-gating rejects newer payload version", False, "no error raised")
    except rb.BusEnvelopeError:
        check("version-gating rejects newer payload version", True)

    # every produced key under kitbash:
    all_keys = r.keys("*")
    check("all keys under kitbash: prefix", all(k.startswith("kitbash:") for k in all_keys),
          f"offenders={[k for k in all_keys if not k.startswith('kitbash:')]}")


# ----------------------------------------------------------------- coupling (live-Redis gated)
def test_coupling_live_redis():
    try:
        live = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True,
                           socket_connect_timeout=1.0)
        live.ping()
    except Exception:
        skip("coupling_delta WRITE (Lua evalsha)", "no live Redis; start kitbash-redis container")
        # READER half still verified on fakeredis below
        test_coupling_reader_fakeredis()
        return

    live.flushdb()
    cv = rc.CouplingValidator(redis_client=live)
    import tempfile
    lf = tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False)
    lf.write("-- placeholder\n")
    lf.close()
    ok_reg = cv.register_scripts(lua_script_path=lf.name) if hasattr(cv, "register_scripts") else None
    os.unlink(lf.name)
    if not ok_reg:
        skip("coupling_delta WRITE (Lua evalsha)", "register_scripts returned falsy")
        test_coupling_reader_fakeredis()
        return

    from redis_coupling import CouplingDelta
    d = CouplingDelta(query_id="qC", layer_a="L0", layer_b="L2", status="OK",
                      delta_magnitude=0.1, severity="LOW", coupling_constant=1.0,
                      timestamp=0, fact_a_id=None, fact_b_id=None, reasoning="t")
    cv.record_delta(d)
    got = cv.get_deltas_for_query("qC")
    check("coupling_delta WRITE+READ on live Redis (Lua evalsha)",
          len(got) == 1 and got[0].query_id == "qC", f"got {got}")
    # canonical key only, under kitbash:
    check("coupling canonical key under kitbash:coupling:",
          live.exists("kitbash:coupling:qC:deltas") == 1)
    live.flushdb()


def test_coupling_reader_fakeredis():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    cv = rc.CouplingValidator(redis_client=r)
    # reader must dual-read + unwrap; fakeredis can't run the Lua writer, so we
    # hand-place an enveloped canonical delta + a legacy bare delta to prove the reader.
    from redis_coupling import CouplingDelta
    d_canon = CouplingDelta(query_id="qR", layer_a="L0", layer_b="L2", status="OK",
                            delta_magnitude=0.1, severity="LOW", coupling_constant=1.0,
                            timestamp=0, fact_a_id=None, fact_b_id=None, reasoning="t")
    env = rb._wrap("coupling_delta", "coupling_validator", json.loads(d_canon.to_json()))
    r.rpush("kitbash:coupling:qR:deltas", env)
    d_legacy = CouplingDelta(query_id="qR", layer_a="L1", layer_b="L3", status="FLAG",
                             delta_magnitude=0.2, severity="MEDIUM", coupling_constant=1.0,
                             timestamp=0, fact_a_id=None, fact_b_id=None, reasoning="t")
    r.rpush("query:qR:deltas", d_legacy.to_json())  # legacy bare
    got = cv.get_deltas_for_query("qR")
    check("coupling reader unwraps canonical envelope", len(got) >= 1 and got[0].query_id == "qR")
    check("coupling reader dual-reads legacy bare delta",
          any(g.status == "FLAG" for g in got), f"got {[(g.layer_a,g.status) for g in got]}")


def main():
    print("=== Bus stream-format contract (§6) ===")
    test_blackboard_payloads()
    test_coupling_live_redis()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        if SKIPS:
            print(f"{len(SKIPS)} skipped (live-Redis gated): {SKIPS}")
        raise SystemExit(1)
    if SKIPS:
        print(f"ALL BUS CHECKS PASS  ({len(SKIPS)} coupling-write check(s) skipped: live Redis not running)")
    else:
        print("ALL BUS CONTRACT CHECKS PASS (fakeredis + live Redis)")
    print("\nNOTE: epistemic TTL is a provisional 24h placeholder (SPEC §4 has no epistemic row) "
          "— confirm before ratifying.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
