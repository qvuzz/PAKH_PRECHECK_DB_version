@echo off
cd /d "%~dp0"

:: Chi tat tien trinh dang chiem port 1234 cua dashboard
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":1234" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

exit
