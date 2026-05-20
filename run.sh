#!/bin/bash
# =========================================================================
#               ActSandbox - Local Manus-like CodeAct Launcher
# =========================================================================
# Portable runner for macOS and Linux

# Ensure script halts on any immediate error
set -e

# Set working directory to the script's location
cd "$(dirname "$0")"

clear
echo "========================================================================="
echo "              ActSandbox - Local Manus-like CodeAct Launcher"
echo "========================================================================="
echo ""

# 1. Check Python installation
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 is not installed or not in PATH. Please install Python 3.11+."
    exit 1
fi
python3 --version

# 2. Check for 'uv' fast package manager
echo "[System] Checking for 'uv' fast package manager..."
USE_UV=0
if command -v uv >/dev/null 2>&1; then
    echo "[System] 'uv' detected! Using uv for ultra-fast setup."
    USE_UV=1
else
    echo "[System] 'uv' not found. Falling back to standard pip."
fi

# 3. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[Setup] Creating Python virtual environment in .venv..."
    if [ $USE_UV -eq 1 ]; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

# 4. Activate Venv and Install Dependencies
echo "[Setup] Activating virtual environment..."
source .venv/bin/activate

echo "[Setup] Installing and updating dependencies..."
if [ $USE_UV -eq 1 ]; then
    uv pip install -r backend/requirements.txt
else
    python3 -m pip install --upgrade pip
    pip install -r backend/requirements.txt
fi

# 5. Create Workspace folder if it doesn't exist
if [ ! -d "workspace" ]; then
    mkdir -p workspace
fi

echo ""
echo "========================================================================="
echo "[Success] ActSandbox environment is fully prepared!"
echo "[System] Starting FastAPI backend server on http://localhost:8000..."
echo "[System] Press Ctrl+C in this window to stop the server."
echo "========================================================================="
echo ""

# Automatically open default browser after 2 seconds in the background
(
    sleep 2
    if command -v open >/dev/null 2>&1; then
        # macOS
        open "http://localhost:8000"
    elif command -v xdg-open >/dev/null 2>&1; then
        # Linux
        xdg-open "http://localhost:8000"
    else
        echo "[System] Please open http://localhost:8000 in your browser manually."
    fi
) &

# Run backend FastAPI server
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
