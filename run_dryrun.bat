@echo off
chcp 65001 >nul
title PAKH Precheck — Dry Run Mode
echo =======================================================
echo    🧪 CHẠY THỬ NGHIỆM DRY-RUN (ĐIỀN THỬ, KHÔNG ĐÓNG THẬT)
echo =======================================================
echo.
cd /d "%~dp0"

python main.py --dry-run --observe --open-excel

echo.
echo =======================================================
echo    ✅ HOÀN TẤT KIỂM THỬ DRY-RUN!
echo =======================================================
pause
