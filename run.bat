@echo off
title ActSandbox Launcher
echo =========================================================================
echo               ActSandbox - Local Manus-like CodeAct Launcher
echo =========================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.11+.
    pause
    exit /b 1
)

:: 2. Check for uv package manager
echo [System] Checking for 'uv' fast package manager...
uv --version >nul 2>&1
set USE_UV=0
if %errorlevel% EQU 0 (
    echo [System] 'uv' detected! Using uv for ultra-fast setup.
    set USE_UV=1
) else (
    echo [System] 'uv' not found. Falling back to standard pip.
)

:: 3. Setup Virtual Environment
if not exist .venv (
    echo [Setup] Creating Python virtual environment in .venv...
    if %USE_UV%==1 (
        uv venv .venv
    ) else (
        python -m venv .venv
    )
)

:: 4. Activate Venv and Install Dependencies
echo [Setup] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [Setup] Installing and updating dependencies...
if %USE_UV%==1 (
    uv pip install -r backend\requirements.txt
) else (
    python -m pip install --upgrade pip
    pip install -r backend\requirements.txt
)

if %errorlevel% NEQ 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

:: 5. Create Workspace folder if not exists
if not exist workspace (
    mkdir workspace
)

echo.
echo =========================================================================
echo [Success] ActSandbox environment is fully prepared!
echo [System] Starting FastAPI backend server on http://localhost:8000...
echo [System] Press Ctrl+C in this window to stop the server.
echo =========================================================================
echo.

:: Automatically open browser after 2 seconds
start "" http://localhost:8000

:: Run backend FastAPI server
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
