"""
TEST-redis_feed.py — integration test for Redis-backed DiagnosticFeed wiring.

Proves the canonical-path wiring (query_orchestrator_factory builds a
RedisDiagnosticFeed against kitbash-redis, and it degrades to no-op when
Redis is down) — the two halves of the "RedisBlackboard core" socket.

Plain script (no pytest), matches repo TEST-* style. Run from repo root:
    python tests/TEST-redis_feed.py
Exit 0 = pass.

Design notes:
  - PATH A (Redis UP) requires the kitbash-redis container (localhost:6379).
    If it is NOT reachable, PATH A is SKIPPED (not failed) so the suite
    stays green when the external container is down — but it prints a note.
  - PATH B (Redis DOWN) needs no server and ALWAYS runs: proves the
    orchestrator-facing feed is safe to call when Redis is unreachable.
"""
import sys, os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

import redis

FEED_KEY = "kitbash:diagnostic:feed"
N_METHODS = ["log_query_created", "log_query_started", "log_query_completed",
              "log_layer_hit", "log_layer_miss", "log_error", "log_metric"]

def _check(cond, msg):
    assert cond, msg
    print(f"  ✓ {msg}")


def path_a_if_redis_up():
    print("\n=== PATH A: kitbash-redis UP (integration) ===")
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    if not r.ping():
        print("  SKIP: kitbash-redis not reachable on :6379 — run `docker start kitbash-redis`")
        return  # not a failure; external container may be down
    r.delete(FEED_KEY)
    from query_orchestrator_factory import create_query_orchestrator
    orch = create_query_orchestrator()
    _check(type(orch.feed).__name__ == "RedisDiagnosticFeed", "factory built RedisDiagnosticFeed")
    _check(orch.feed._alive is True, "feed reports alive against kitbash-redis")
    # exercise every DiagnosticFeed method the orchestrator calls
    orch.feed.log_query_created("qA1", "what is ATP?")
    orch.feed.log_query_started("qA1")
    orch.feed.log_layer_hit("qA1", "CARTRIDGE", 0.75)
    orch.feed.log_layer_miss("qA1", "GRAIN", 0.10, 0.70)
    orch.feed.log_error("qA1", "X", "boom")
    orch.feed.log_query_completed("qA1", "CARTRIDGE", 0.75, 32.1)
    orch.feed.log_metric("queries_answered", 1)
    raw = r.lrange(FEED_KEY, 0, -1)
    r.delete(FEED_KEY)
    _check(len(raw) == len(N_METHODS), f"all {len(N_METHODS)} feed calls persisted ({len(raw)})")
    for x in raw:
        _check(x.startswith('{"v": 1, "schema": "diagnostic_event@1"'), x[:80])
    print(f"  ✓ {len(raw)} diagnostic_event@1 envelopes written + well-formed")


def path_b_redis_down():
    print("\n=== PATH B: Redis DOWN (graceful no-op) ===")
    import redis_blackboard as rb
    dead = rb.RedisDiagnosticFeed(
        redis_client=redis.Redis(host="localhost", port=6399, db=0,
                                 decode_responses=True, socket_connect_timeout=1))
    _check(dead._alive is False, "dead feed reports not-alive")
    # none of these may raise, even with Redis unreachable
    dead.log_query_created("qB1", "x")
    dead.log_query_started("qB1")
    dead.log_layer_hit("qB1", "GRAIN", 0.1)
    dead.log_layer_miss("qB1", "GRAIN", 0.1, 0.7)
    dead.log_error("qB1", "X", "boom")
    dead.log_query_completed("qB1", "NONE", 0.0, 1.0)
    dead.log_metric("m", 1)
    _check(True, "all log_* calls no-op without raising when Redis down")


if __name__ == "__main__":
    try:
        path_a_if_redis_up()
        path_b_redis_down()
        print("\nRESULT: TEST-redis_feed PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
