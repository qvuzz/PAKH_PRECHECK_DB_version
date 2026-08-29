@echo off
cd /d "%~dp0"

:: 1. Clean up old process on port 1234 if any
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":1234" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 2. Launch Dashboard silently via pythonw
start "" pythonw dashboard.py

:: 3. Wait 1.5s and exit (dashboard.py will automatically open the tab in Chrome Debug)
ping 127.0.0.1 -n 2 >nul
exit
