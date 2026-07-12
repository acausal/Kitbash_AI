"""
kitbash_cli.py — stdio JSON bridge for the Kitbash query orchestrator.

Purpose (first-MVP POC):
  - One channel for the chat UI (stdout): ONLY clean chat JSON.
  - One channel for ops/logs/streams (stderr): internal operational detail.

Protocol (newline-delimited JSON on each side):

  stdin  -> {"query": "..."}            (one JSON object per line)
  stdout -> {"type":"answer_chunk","text":"..."}
           {"type":"answer_done","query_id":...,"engine":...,"confidence":...}
  stderr -> plain Python logging (level INFO+) + {"ops":...} structured lines

The web UI spawns this process, writes requests to stdin, reads chat JSON
from stdout, and tails stderr for debugging/telemetry. Streaming is v1
"fake-chunk": the final answer is emitted in word-ish chunks so the wire
format supports real token streaming later (drop-in at the engine layer).

Config: enable/disable engines via env (KITBASH_ENABLE_BITNET / _MAMBA),
default both ON for the POC since both sockets are GREEN.
"""

import sys
import os
import json
import logging
import time
import contextlib

# Make repo root importable when run as a bare script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query_orchestrator_factory import create_query_orchestrator


def _emit_stdout(obj: dict) -> None:
    """Write a single chat-facing JSON line to stdout (flushed)."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _build_orchestrator():
    enable_bitnet = os.environ.get("KITBASH_ENABLE_BITNET", "1") != "0"
    enable_mamba = os.environ.get("KITBASH_ENABLE_MAMBA", "1") != "0"
    # Redirect any in-process prints (e.g. MTR state banner) to stderr during
    # build so the stdout chat channel stays clean. Subprocess output (e.g.
    # BitMamba autostart) is already routed to stderr by the engine.
    with contextlib.redirect_stdout(sys.stderr):
        return create_query_orchestrator(
            enable_bitnet=enable_bitnet,
            enable_mamba=enable_mamba,
            # BitMamba autostarts its server if not already running.
            mamba_autostart=True,
        )


def _chunk(text: str, size: int = 12):
    """Yield word-ish chunks for v1 fake streaming."""
    words = text.split(" ")
    buf = ""
    for w in words:
        buf += ("" if not buf else " ") + w
        if len(buf) >= size:
            yield buf
            buf = ""
    if buf:
        yield buf


def handle_query(orchestrator, user_query: str) -> None:
    """Run one query; emit chat JSON on stdout, ops already on stderr."""
    t0 = time.perf_counter()
    result = orchestrator.process_query(user_query)
    latency_ms = (time.perf_counter() - t0) * 1000

    answer = result.answer or ""
    # v1 fake streaming: emit chunks so the UI can render progressively.
    for piece in _chunk(answer):
        _emit_stdout({"type": "answer_chunk", "text": piece})

    _emit_stdout({
        "type": "answer_done",
        "query_id": result.query_id,
        "engine": result.engine_name,
        "confidence": result.confidence,
        "mamba_injected": getattr(result, "mamba_injected", False),
        "total_latency_ms": round(latency_ms, 1),
    })
    # Ops note on stderr (chat channel stays clean).
    logging.info(
        "query=%s engine=%s conf=%.3f latency_ms=%.1f layers=%d",
        result.query_id[:8], result.engine_name, result.confidence,
        latency_ms, len(result.layer_results),
    )


def main() -> int:
    # logging -> stderr (NOT stdout) so the chat channel stays clean.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("kitbash_cli")

    log.info("kitbash_cli starting; building orchestrator...")
    try:
        orchestrator = _build_orchestrator()
    except Exception as e:
        log.exception("orchestrator build failed: %s", e)
        _emit_stdout({"type": "error", "message": f"orchestrator build failed: {e}"})
        return 1
    log.info("orchestrator ready")

    # Read newline-delimited JSON requests from stdin until EOF.
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning("bad stdin JSON: %s", e)
                _emit_stdout({"type": "error", "message": f"bad request: {e}"})
                continue

            user_query = req.get("query")
            if not isinstance(user_query, str) or not user_query.strip():
                _emit_stdout({"type": "error", "message": "missing 'query' string"})
                continue

            try:
                handle_query(orchestrator, user_query)
            except Exception as e:
                log.exception("query failed: %s", e)
                _emit_stdout({"type": "error", "message": f"query failed: {e}"})
    finally:
        # Persist the async dream-bucket trace queue + MTR state before exit.
        try:
            orchestrator.close()
        except Exception as e:
            log.warning("orchestrator close failed: %s", e)

    log.info("stdin closed; kitbash_cli exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
