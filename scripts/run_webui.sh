#!/usr/bin/env bash
# run_webui.sh — detached, self-restarting watchdog for kitbash_web.py.
#
# Why: the webui used to be launched with a plain `nohup ... &` inside a
# foreground launcher; when that shell/turn ended, the child was reaped and
# the server "kept dying". This script runs an infinite restart loop and is
# itself launched with `nohup ... & disown` (no setsid on this host), so it
# detaches from the controlling terminal and survives the launcher's exit.
# The loop restarts the webui within ~2s if it ever exits/crashes.
#
# PATH HANDLING (critical on this MSYS/git-bash host):
#   - Resolve REPO to a backslash Windows path via `cygpath -w` so the venv
#     python command path is never mangled.
#   - Invoke the webui with a RELATIVE path (`kitbash_web.py`) while cwd is the
#     repo. Passing an absolute /c/... or C:/... path as an ARG triggers MSYS
#     double-conversion (C:\c\...) and the file open fails with rc=2.

set -uo pipefail

REPO="$(cygpath -w "$(cd "$(dirname "$0")/.." && pwd)" 2>/dev/null)"
[ -z "$REPO" ] && REPO="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
cd "$REPO" || { echo "[webui-watchdog] ERROR: cannot cd to $REPO" >>/tmp/kitbash_web.log; exit 1; }

if [ -x "$REPO/.venv/Scripts/python.exe" ]; then
    VENV_PY="$REPO/.venv/Scripts/python.exe"
else
    echo "[webui-watchdog] ERROR: no .venv python at $REPO/.venv" >>/tmp/kitbash_web.log
    exit 1
fi

echo "[webui-watchdog] starting; python=$VENV_PY repo=$REPO" >>/tmp/kitbash_web.log
while true; do
    # Relative path arg avoids MSYS C:\c\... double-conversion (cwd = repo).
    "$VENV_PY" kitbash_web.py >>/tmp/kitbash_web.log 2>&1
    echo "[webui-watchdog] webui exited (rc=$?) at $(date); restarting in 2s" >>/tmp/kitbash_web.log
    sleep 2
done
