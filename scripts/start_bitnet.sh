#!/usr/bin/env bash
# start_bitnet.sh — launch the BitNet inference server with the stable config.
#
# BitNet = the CPU-efficient low-bit tier of the cascade. This build of
# llama.cpp is CPU-ONLY (no cuda/cublas DLLs), so -ngl is a no-op and BitNet
# uses ~0 VRAM — the GPU stays reserved for the eventual quantized synthesis LLM.
# Memory budget here is SYSTEM RAM (weights ~2.2GB + KV-cache ~1280 MiB @ -c 4096).
#
# This is the DEFINED "bounded fallback/efficiency mode". -c can go higher freely
# (RAM cost only); keep it sane so BitNet + BitMamba + a CPU synthesis model coexist.
#
# Override any value via env, e.g.:  BITNET_CTX=8192 ./scripts/start_bitnet.sh
set -euo pipefail

BITNET_BIN="${BITNET_BIN:-B:/ai/llm/kitbash/bitnet/build/bin/llama-server.exe}"
BITNET_MODEL="${BITNET_MODEL:-B:/ai/llm/kitbash/bitnet/models/BitNet-b1_58-3B/Little-Bitch-3B.i1-Q6_K.gguf}"
BITNET_HOST="${BITNET_HOST:-127.0.0.1}"
BITNET_PORT="${BITNET_PORT:-8080}"
BITNET_CTX="${BITNET_CTX:-4096}"     # total context: prompt + generation
BITNET_NGL="${BITNET_NGL:-0}"        # no-op on this CPU-only build; kept for clarity
BITNET_THREADS="${BITNET_THREADS:-4}" # CPU-only: pin to PHYSICAL cores (4), not HT (8)

BIN_DIR="$(dirname "$BITNET_BIN")"
EXE_NAME="$(basename "$BITNET_BIN")"

echo "[start_bitnet] config: ctx=$BITNET_CTX host=$BITNET_HOST port=$BITNET_PORT (CPU-only; -ngl=$BITNET_NGL is a no-op)"

# --- sanity checks ---
[ -f "$BITNET_BIN" ]   || { echo "[start_bitnet] ERROR: binary not found: $BITNET_BIN" >&2; exit 1; }
[ -f "$BITNET_MODEL" ] || { echo "[start_bitnet] ERROR: model not found: $BITNET_MODEL" >&2; exit 1; }

# --- stop any existing instance (idempotent restart) ---
if MSYS2_ARG_CONV_EXCL='*' taskkill /IM "$EXE_NAME" /F >/dev/null 2>&1; then
    echo "[start_bitnet] stopped existing $EXE_NAME"
    sleep 2
fi

# --- launch in foreground (exec) ---
# This script does NOT self-detach — run it backgrounded by the caller, e.g.:
#   nohup bash scripts/start_bitnet.sh >/tmp/bitnet.log 2>&1 &
# or via a process manager / Hermes terminal(background=true).
# Readiness: poll http://HOST:PORT/health until 200 in a separate shell.
cd "$BIN_DIR"
echo "[start_bitnet] launching $EXE_NAME (foreground; ctx=$BITNET_CTX)..."
exec env MSYS2_ARG_CONV_EXCL='*' "./$EXE_NAME" \
    --model "$BITNET_MODEL" \
    -c "$BITNET_CTX" \
    -ngl "$BITNET_NGL" \
    -t "$BITNET_THREADS" \
    --host "$BITNET_HOST" \
    --port "$BITNET_PORT"
