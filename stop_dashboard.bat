@echo off
cd /d "%~dp0"

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":1234" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=2" %%i in ('tasklist /fi "imagename eq pythonw.exe" /nh') do (
    taskkill /f /pid %%i >nul 2>&1
)

exit
