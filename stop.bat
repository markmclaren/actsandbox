@echo off
title ActSandbox Stopper
echo =========================================================================
echo               ActSandbox - Stopper and Cleanup Utility
echo =========================================================================
echo.

:: 1. Stop FastAPI Backend Process
echo [Cleanup] Checking for processes running on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo [Cleanup] Found process PID %%a listening on port 8000. Terminating...
    taskkill /f /pid %%a >nul 2>&1
)

echo [Cleanup] Checking for running Uvicorn/Python processes...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /fi "windowtitle eq ActSandbox Launcher*" >nul 2>&1

:: 2. Cleanup Lingering Docker Sandbox Containers
echo [Cleanup] Checking for lingering ActSandbox Docker containers...
docker ps -a --filter "name=act-sandbox-" --format "{{.Names}}" > "%temp%\containers.txt" 2>nul

set HAS_CONTAINERS=0
for /f "tokens=*" %%c in ("%temp%\containers.txt") do (
    set HAS_CONTAINERS=1
)

if exist "%temp%\containers.txt" (
    for /f "usebackq tokens=*" %%c in ("%temp%\containers.txt") do (
        echo [Cleanup] Stopping and removing container: %%c
        docker stop %%c >nul 2>&1
        docker rm %%c >nul 2>&1
    )
)
del "%temp%\containers.txt" >nul 2>&1

echo.
echo =========================================================================
echo [Success] ActSandbox has been completely stopped and cleaned up!
echo =========================================================================
echo.
timeout /t 3
exit
