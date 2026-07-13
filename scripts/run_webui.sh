#!/usr/bin/env bash
# run_webui.sh — DISABLED.
# The kitbash webui auto-launch is currently STOPPED (user request, 2026-07-13).
# This no-op prevents the external watchdog/respawner from starting the webui
# while still exiting cleanly (so the respawner does not churn on launch failure).
#
# To re-enable the self-restarting webui watchdog, restore the real script:
#   git checkout scripts/run_webui.sh
exit 0
