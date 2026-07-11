"""
TEST-kitbash_cli.py — contract test for kitbash_cli.py stdio JSON bridge.

Run:  .venv\\Scripts\\activate && python TEST-kitbash_cli.py

Locks in the CLI protocol contract (the "chat-only stdout / ops-on-stderr"
split that the web-UI POC depends on):
  - stdout is newline-delimited JSON, every line a {"type":...} object
    (chat channel only; no internal ops/MTR banner leakage).
  - final chat line is {"type":"answer_done", ...} with engine + confidence.
  - stderr carries internal operational logs (non-empty).
  - malformed/empty request -> an {"type":"error",...} chat line, no crash.

Runs the CLI as a subprocess against live engines (BitNet + BitMamba both
wired; BitMamba autostarts). No pytest.
"""

import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(REPO, "kitbash_cli.py")


def _run_cli(stdin_text: str):
    return subprocess.run(
        [sys.executable, CLI],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
    )


def _assert_chat_only(stdout: str):
    lines = [l for l in stdout.splitlines() if l.strip()]
    assert lines, "stdout empty"
    for l in lines:
        obj = json.loads(l)
        assert "type" in obj, f"stdout line missing 'type': {l}"
    # No internal ops leakage (the specific MTR state banner print).
    assert not any("MTR state loaded" in l for l in lines), \
        "internal MTR banner leaked to chat channel!"
    return lines


def main() -> int:
    # 1. Normal query: chat-only stdout, ops on stderr, answer_done present.
    proc = _run_cli('{"query":"What is entropy?"}\n')
    assert proc.returncode == 0, f"CLI rc={proc.returncode}, stderr={proc.stderr[-500:]}"
    out = _assert_chat_only(proc.stdout)
    assert any(json.loads(l).get("type") == "answer_chunk" for l in out), \
        "no answer_chunk in chat output"
    done = [json.loads(l) for l in out if json.loads(l).get("type") == "answer_done"]
    assert done, "no answer_done"
    assert done[0].get("engine") and isinstance(done[0].get("confidence"), (int, float)), \
        "answer_done missing engine/confidence"
    assert [l for l in proc.stderr.splitlines() if l.strip()], "stderr ops channel empty"
    print(f"[1] normal query: stdout chat-only ({len(out)} lines), "
          f"engine={done[0]['engine']}, conf={done[0]['confidence']}: OK")

    # 2. Malformed request -> error chat line, no crash, rc==0.
    proc2 = _run_cli('not-json-at-all\n')
    assert proc2.returncode == 0, f"malformed rc={proc2.returncode}"
    out2 = _assert_chat_only(proc2.stdout)
    assert any(json.loads(l).get("type") == "error" for l in out2), \
        "malformed request did not produce an error line"
    print(f"[2] malformed request -> error line, no crash: OK")

    # 3. Missing query field -> error chat line, no crash.
    proc3 = _run_cli('{"foo":"bar"}\n')
    assert proc3.returncode == 0, f"missing-query rc={proc3.returncode}"
    out3 = _assert_chat_only(proc3.stdout)
    assert any(json.loads(l).get("type") == "error" for l in out3), \
        "missing-query did not produce an error line"
    print(f"[3] missing 'query' field -> error line, no crash: OK")

    print("\nRESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"\nRESULT: FAIL — {e}")
        sys.exit(1)
