#!/usr/bin/env bash
# start_kitbash_stack.sh — bring up the Kitbash stack for usage-mode testing.
#
# Idempotent: checks each port, only starts what is missing. Always launches
# the webui under the repo .venv python (NEVER bare `python` — the system uv
# python lacks torch and reproduces the KitbashMTREngine NameError).
#
# BitMamba2 is NOT launched here: the CLI autostarts bitmamba_server.exe per
# query (mamba_autostart=True in kitbash_cli.py). Redis (kitbash-redis) is an
# external Docker container — this script only warns if it is down.
#
# Usage:  bash scripts/start_kitbash_stack.sh
# Then open http://127.0.0.1:8777

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

# --- the one rule that matters: use the venv python, not system `python` ---
if [ -x "$REPO/.venv/Scripts/python.exe" ]; then
    VENV_PY="$REPO/.venv/Scripts/python.exe"
elif [ -x "$REPO/.venv/bin/python" ]; then
    VENV_PY="$REPO/.venv/bin/python"
else
    echo "[launcher] ERROR: no .venv python at $REPO/.venv — refusing to start webui under a possibly-torch-less system python."
    exit 1
fi

port_up() {  # $1 = port; returns 0 if something listens
    curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$1/" >/dev/null 2>&1 \
        || curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$1/health" >/dev/null 2>&1
}

# kill only the process listening on a given port (precise; never image-wide)
kill_port() {
    local port="$1"
    local pid
    pid=$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | grep -oE '[0-9]+$' | head -1)
    if [ -n "$pid" ]; then
        MSYS2_ARG_CONV_EXCL='*' taskkill /PID "$pid" /F >/dev/null 2>&1 && echo "[kill] stopped pid $pid on :$port"
    fi
}

# verify a listening port is owned by the venv python (check CommandLine, NOT
# ExecutablePath — under git-bash the latter reports the parent bash host)
verify_venv_webui() {
    local pid
    pid=$(netstat -ano 2>/dev/null | grep ':8777 ' | grep LISTENING | grep -oE '[0-9]+$' | head -1)
    [ -z "$pid" ] && { echo "[webui] not listening"; return 1; }
    local cmd
    cmd=$(wmic process where "ProcessId=$pid" get CommandLine 2>/dev/null | grep -i python | head -1)
    if echo "$cmd" | grep -qi "Kitbash_AI/.venv"; then
        echo "[webui] OK — pid $pid on .venv python ($cmd)"
        return 0
    fi
    echo "[webui] WARNING — pid $pid not on .venv: $cmd"
    return 1
}

echo "=== Kitbash stack launcher (repo: $REPO) ==="
echo "[launcher] python = $VENV_PY"

# 1) BitNet inference server (:8080)
if port_up 8080; then
    echo "[bitnet] :8080 already up — skipping"
else
    echo "[bitnet] :8080 down — launching via start_bitnet.sh (CPU-only, -t 4)"
    nohup bash "$REPO/scripts/start_bitnet.sh" >/tmp/bitnet.log 2>&1 &
    for i in $(seq 1 30); do
        if port_up 8080; then echo "[bitnet] healthy after ~$((i*3))s"; break; fi
        sleep 3
    done
    port_up 8080 && echo "[bitnet] OK" || echo "[bitnet] WARNING: still not healthy (see /tmp/bitnet.log)"
fi

# 2) Redis (external Docker) — warn only
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^kitbash-redis$'; then
    echo "[redis] kitbash-redis container up"
else
    echo "[redis] WARNING: kitbash-redis not running — start it (Docker) or the DiagnosticFeed degrades to no-op. Stack still works without it."
fi

# 3) Web UI (:8777) — under the venv python, always (restart to guarantee interpreter)
if port_up 8777; then
    echo "[webui] :8777 up — restarting under venv python to guarantee correct interpreter"
    kill_port 8777
    sleep 2
fi
echo "[webui] launching kitbash_web.py under $VENV_PY"
nohup "$VENV_PY" "$REPO/kitbash_web.py" >/tmp/kitbash_web.log 2>&1 &
for i in $(seq 1 15); do
    if port_up 8777; then echo "[webui] listening after ~$((i*2))s"; break; fi
    sleep 2
done
verify_venv_webui || echo "[webui] WARNING: webui not on .venv python (queries may fail with NameError)."

# 4) BitMamba2 — autostarted per query by the CLI; nothing to launch here.
echo "[mamba] BitMamba2 autostarts per-query via kitbash_cli (mamba_autostart=True)."

echo "=== stack launcher done ==="
