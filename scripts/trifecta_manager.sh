#!/bin/bash
# scripts/trifecta_manager.sh - Authoritative lifecycle manager for Trifecta Daemon
# Standard F1 Engine Orchestration v2 (Stage 3 Deep Intel)

set -euo pipefail

REPO_ID="d21bfdd6"
PID_FILE="$HOME/.local/share/trifecta/repos/$REPO_ID/runtime/daemon/pid"
LOCK_FILE="$HOME/.local/share/trifecta/repos/$REPO_ID/runtime/daemon/lock"
STATUS_JSON="_ctx/telemetry/daemon.status"

# Multi-tier resilient binary detection
if command -v trifecta >/dev/null 2>&1 && trifecta graph --help >/dev/null 2>&1; then
    TRIFECTA_BIN="trifecta"
elif [[ -f "./.venv/bin/trifecta" ]]; then
    TRIFECTA_BIN="./.venv/bin/trifecta"
elif command -v uv >/dev/null 2>&1 && [[ -f "pyproject.toml" ]]; then
    TRIFECTA_BIN="uv run trifecta"
else
    # Total fallback: notify agent
    echo "[trifecta-manager] CRITICAL: Valid 'trifecta' binary with Graph support not found."
    echo "Hint: Install latest trifecta or initialize a uv environment."
    exit 1
fi

# Ensure telemetry dir exists
mkdir -p _ctx/telemetry

_update_status_json() {
    local pid="${1:-0}"
    local status="${2:-unknown}"
    local now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Sanitize PID
    pid="${pid//[^0-9]/}"
    pid="${pid:-0}"

    cat <<EOF > "$STATUS_JSON"
{
  "pid": $pid,
  "status": "$status",
  "last_check": "$now",
  "repo_id": "$REPO_ID"
}
EOF
}

_is_process_running() {
    local pid="$1"
    if [[ -z "$pid" ]] || [[ "$pid" == "0" ]]; then return 1; fi
    # Check if process exists AND is a trifecta daemon
    if ps -p "$pid" > /dev/null 2>&1; then
        if ps -p "$pid" -o args= 2>/dev/null | grep -q "daemon"; then
            return 0
        fi
    fi
    return 1
}

_prune_zombies() {
    local current_pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
    if ! _is_process_running "$current_pid"; then
        echo "[trifecta-manager] Pruning stale state (PID $current_pid not found)..."
        rm -f "$PID_FILE" "$LOCK_FILE"
    fi
}

_check_lsp_binary() {
    if command -v pyright >/dev/null 2>&1 || command -v pylsp >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

status() {
    local pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
    if _is_process_running "$pid"; then
        echo "Daemon: running (PID: $pid)"
        _update_status_json "$pid" "running"
        return 0
    else
        echo "Daemon: stopped"
        _update_status_json 0 "stopped"
        return 1
    fi
}

start() {
    _prune_zombies
    local pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
    if _is_process_running "$pid"; then
        echo "Daemon already running (PID: $pid)"
        return 0
    fi

    if ! _check_lsp_binary; then
        echo "[trifecta-manager] WARNING: No LSP binary (pyright/pylsp) found. Daemon will run in AST-only mode."
    fi

    echo "[trifecta-manager] Starting daemon..."
    if $TRIFECTA_BIN daemon start --repo . > /dev/null 2>&1; then
        sleep 1
        local new_pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
        if _is_process_running "$new_pid"; then
            echo "Daemon started successfully (PID: $new_pid)"
            _update_status_json "$new_pid" "running"
            return 0
        fi
    fi

    echo "ERROR: Failed to start daemon"
    _update_status_json 0 "error"
    return 1
}

stop() {
    local pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
    if _is_process_running "$pid"; then
        echo "[trifecta-manager] Stopping daemon (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
    # Hard cleanup
    rm -f "$PID_FILE" "$LOCK_FILE"
    echo "Daemon stopped"
    _update_status_json 0 "stopped"
}

restart() {
    stop
    start
}

health() {
    local pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
    if ! _is_process_running "$pid"; then
        echo "[trifecta-manager] Unhealthy state detected. Attempting recovery..."
        start
    else
        echo "Daemon is healthy (PID: $pid)"
        _update_status_json "$pid" "healthy"
    fi
}

warmup() {
    echo "[trifecta-manager] Launching Ignition Sequence (Full Stack)..."
    
    echo "[1/3] Building Context Pack (sync)..."
    if $TRIFECTA_BIN ctx sync --segment . ; then
        echo "✅ Context synchronized and chunks generated."
    else
        echo "❌ FAILED: Context sync failed."
        exit 1
    fi

    echo "[2/3] Building Symbol Graph (graph index)..."
    if $TRIFECTA_BIN graph index --segment . ; then
        echo "✅ Graph built successfully."
    else
        echo "❌ FAILED: Graph build failed."
        exit 1
    fi

    echo "[3/3] Starting Daemon (LSP)..."
    start
    
    echo ""
    echo "=== F1 ENGINE SOVEREIGN BIRTH COMPLETE ==="
    echo "Context built, Graph indexed, Daemon alive."
    echo "The repository is now fully operational for AI Agents."
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    health) health ;;
    warmup) warmup ;;
    *) echo "Usage: $0 {start|stop|restart|status|health|warmup}"; exit 1 ;;
esac
