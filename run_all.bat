@echo off
chcp 65001 >nul
title PAKH Precheck — Auto Run All Pipeline
echo =======================================================
echo    🚀 KHỞI CHẠY TRỌN GÓI PAKH PRECHECK VNPT (1-CLICK)
echo =======================================================
echo.
cd /d "%~dp0"

python main.py --auto-close --open-excel

echo.
echo =======================================================
echo    ✅ HOÀN TẤT TOÀN BỘ TIẾN TRÌNH!
echo =======================================================
pause
