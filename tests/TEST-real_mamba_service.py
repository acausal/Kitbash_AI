"""
TEST-real_mamba_service.py — contract test for RealMambaService (Option B2).

Run:  .venv\\Scripts\\activate && python TEST-real_mamba_service.py

Verifies:
  - RealMambaService is a MambaContextService subclass; get_context returns a
    MambaContext, never None.
  - With a reachable server + user_query: context_1hour populated, the three
    longer windows EMPTY (honest Option 1 mapping), active_topics extracted.
  - Graceful degradation: disabled -> empty-but-valid; unreachable port ->
    empty-but-valid, no exception escapes.

The live test (test_live_mapping_option1) uses autostart to launch
bitmamba_server itself if the engine is built on this machine. If the engine is
absent, that test is SKIPPED (not failed) so the file stays runnable in a bare
checkout.

No pytest dependency — plain asserts, exit 0 on all-pass.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces.mamba_context_service import MambaContextService, MambaContext, MambaContextRequest
from real_mamba_service import RealMambaService


ENGINE_TREE = "B:/ai/llm/kitbash/bitmamba.cpp"
EXE = os.path.join(ENGINE_TREE, "build", "Release", "bitmamba_server.exe")
MODEL = "B:/ai/llm/kitbash/models/bitmamba/bitmamba_255m.bin"


def _have_engine() -> bool:
    return os.path.exists(EXE) and os.path.exists(MODEL)


def main() -> int:
    fails = []

    # 1. subclass contract
    assert issubclass(RealMambaService, MambaContextService), "not a MambaContextService"
    print("[1] subclass contract: OK")

    # 2. never returns None
    svc = RealMambaService(enabled=False)
    ctx = svc.get_context(MambaContextRequest(user_query="x"))
    assert isinstance(ctx, MambaContext) and ctx is not None
    print("[2] never None: OK")

    # 3. disabled -> empty-but-valid
    assert ctx.context_1hour == {} and ctx.active_topics == [], "disabled should be empty"
    print("[3] disabled empty: OK")

    # 4. unreachable -> graceful empty, no raise
    svc_bad = RealMambaService(host="127.0.0.1", port=9999, enabled=True, autostart=False)
    ctx_bad = svc_bad.get_context(MambaContextRequest(user_query="x"))
    assert isinstance(ctx_bad, MambaContext) and ctx_bad.context_1hour == {}
    print("[4] unreachable graceful: OK")

    # 5. live mapping (Option 1) — autostart the engine if present
    if not _have_engine():
        print("[5] SKIPPED (bitmamba_server engine not built on this machine)")
    else:
        svc_live = RealMambaService(
            host="127.0.0.1", port=8741,
            model_path=MODEL, exe_path=EXE, cwd=ENGINE_TREE,
            enabled=True, autostart=True, timeout=60.0,
        )
        try:
            ctx_live = svc_live.get_context(MambaContextRequest(user_query="What is a ribosome?"))
            assert isinstance(ctx_live, MambaContext)
            assert ctx_live.context_1hour, "context_1hour should be populated from live model"
            assert ctx_live.active_topics, "active_topics should be extracted"
            # honest mapping: the three longer windows stay empty (stateless model)
            assert ctx_live.context_1day == {}, "context_1day must stay empty (Option 1)"
            assert ctx_live.context_72hours == {}, "context_72hours must stay empty (Option 1)"
            assert ctx_live.context_1week == {}, "context_1week must stay empty (Option 1)"
            print(f"[5] live Option-1 mapping: OK "
                  f"(1hour len={len(str(ctx_live.context_1hour.get('generated','')))}, "
                  f"topics={ctx_live.active_topics})")
        finally:
            svc_live.shutdown()

    print("\nRESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\nRESULT: FAIL — {e}")
        sys.exit(1)
