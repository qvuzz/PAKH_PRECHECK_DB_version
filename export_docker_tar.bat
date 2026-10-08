@echo off
chcp 65001 >nul
echo ==============================================================================
echo   VNPT VINAPHONE - DOCKER BUILD ^& EXPORT IMAGE (.TAR)
echo   Du an: PAKH Precheck Web Dashboard
echo ==============================================================================
echo.

:: 1. Kiem tra Docker Daemon
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Docker chua duoc khoi dong hoac chua duoc cai dat tren may.
    echo Vui long mo Docker Desktop truoc khi chay script nay.
    pause
    exit /b 1
)

:: 2. Chuan bi file .env neu chua co
if not exist ".env" (
    if exist ".env.sample" (
        echo [INFO] Dang tao file .env tu .env.sample...
        copy /y ".env.sample" ".env" >nul
    )
)

:: 3. Chuan bi cac file du lieu de tranh Docker tao nham thanh thu muc
if not exist "tickets.db" (
    echo. > "tickets.db"
)
if not exist "btools_cookie.json" (
    echo {} > "btools_cookie.json"
)
if not exist "cem_auth_cache.json" (
    echo {} > "cem_auth_cache.json"
)
if not exist "ttsnew_token_cache.json" (
    echo {} > "ttsnew_token_cache.json"
)
if not exist "lan_sessions.json" (
    echo {} > "lan_sessions.json"
)
if not exist "ccos_cookie_cache.json" (
    echo {} > "ccos_cookie_cache.json"
)
if not exist "sapccheck\sapc_cookies.json" (
    if not exist "sapccheck" mkdir "sapccheck"
    echo [] > "sapccheck\sapc_cookies.json"
)
if not exist "result" mkdir "result"
if not exist "scratch" mkdir "scratch"
if not exist "models" mkdir "models"

echo [1/2] Dang tien hanh Build Docker Image: pakh_precheck:latest...
echo (Qua trinh nay co the mat 1-3 phut tuy thuoc vao toc do mang)...
echo.
docker build -t pakh_precheck:latest .

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Qua trinh Build Docker Image that bai!
    pause
    exit /b 1
)

echo.
echo [2/2] Dang nen Docker Image ra file: pakh_precheck_image.tar...
docker save -o pakh_precheck_image.tar pakh_precheck:latest

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Xuat file .tar that bai!
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo  HOAN TAT DONG GOI DOCKER IMAGE THANH CONG!
echo ==============================================================================
echo File da tao: pakh_precheck_image.tar
echo.
echo HUONG DAN TRIEN KHAI TREN MAY CHU SERVER (Linux / Windows Server):
echo ------------------------------------------------------------------------------
echo 1. Copy cac file sau sang thu muc tren may chu:
echo    - pakh_precheck_image.tar
echo    - docker-compose.yml
echo    - .env.sample (doi ten thanh .env tren server)
echo    - thu muc models/ (copy file qwen2.5-3b-instruct-q4_k_m.gguf vao day neu dung Qwen AI)
echo    - tickets.db (neu muon mang theo CSDL cu)
echo.
echo 2. Tren may chu server, mo Terminal va chay 2 lenh sau:
echo    docker load -i pakh_precheck_image.tar
echo    docker compose up -d
echo.
echo 3. Kiem tra container dang chay:
echo    docker compose ps
echo    Xem log: docker compose logs -f
echo    Truy cap: http://^<IP_SERVER^>:1234
echo ==============================================================================
pause
