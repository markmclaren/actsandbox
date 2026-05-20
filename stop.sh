#!/bin/bash
# =========================================================================
#               ActSandbox - Stopper and Cleanup Utility
# =========================================================================
# Portable stopper and resource cleaner for macOS and Linux

# Set working directory to the script's location
cd "$(dirname "$0")"

clear
echo "========================================================================="
echo "              ActSandbox - Stopper and Cleanup Utility"
echo "========================================================================="
echo ""

# 1. Stop FastAPI Backend Process
echo "[Cleanup] Checking for processes running on port 8000..."
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -t -i:8000)
    if [ ! -z "$PID" ]; then
        echo "[Cleanup] Found process PID $PID listening on port 8000. Terminating..."
        kill -9 $PID >/dev/null 2>&1 || true
    else
        echo "[Cleanup] No processes running on port 8000."
    fi
else
    # Fallback to process search
    echo "[Cleanup] 'lsof' not found. Falling back to process kill..."
    pkill -9 -f "uvicorn backend.app:app" >/dev/null 2>&1 || true
fi

# 2. Cleanup Lingering Docker Sandbox Containers
echo "[Cleanup] Checking for lingering ActSandbox Docker containers..."
if command -v docker >/dev/null 2>&1; then
    # Get any containers with "act-sandbox-" in the name
    CONTAINERS=$(docker ps -a --filter "name=act-sandbox-" --format "{{.Names}}")
    
    if [ ! -z "$CONTAINERS" ]; then
        for c in $CONTAINERS; do
            echo "[Cleanup] Stopping and removing container: $c"
            docker stop "$c" >/dev/null 2>&1 || true
            docker rm "$c" >/dev/null 2>&1 || true
        done
    else
        echo "[Cleanup] No lingering ActSandbox Docker containers found."
    fi
else
    echo "[System] Docker not detected. Skipping container cleanup."
fi

echo ""
echo "========================================================================="
echo "[Success] ActSandbox has been completely stopped and cleaned up!"
echo "========================================================================="
echo ""
sleep 2
