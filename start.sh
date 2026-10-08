#!/bin/bash
# ==============================================================================
# Script Khoi Dong PAKH Precheck tren Linux Server
# ==============================================================================
set -e

echo "=== [PAKH PRECHECK] Dang chuan bi moi truong tren Server ==="

# 1. Tao cac file du lieu can thiet de Docker khong mount nham thanh thu muc
mkdir -p result scratch models sapccheck templates static routers services

# Kiem tra neu tickets.db bi loi (malformed) thi tu dong backup va lam sach
if [ -f tickets.db ] && [ -s tickets.db ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        if ! sqlite3 tickets.db "PRAGMA quick_check;" >/dev/null 2>&1; then
            echo "[CANH BAO] File tickets.db tren may chu bi loi hỏng (malformed)."
            echo "[INFO] Dang tu dong sao luu va tao lai file database sach..."
            mv tickets.db "tickets.db.malformed_$(date +%Y%m%d_%H%M%S).bak"
            rm -f tickets.db-wal tickets.db-shm
        fi
    fi
fi

[ -f tickets.db ] || touch tickets.db
[ -f btools_cookie.json ] || echo "{}" > btools_cookie.json
[ -f cem_auth_cache.json ] || echo "{}" > cem_auth_cache.json
[ -f ttsnew_token_cache.json ] || echo "{}" > ttsnew_token_cache.json
[ -f lan_sessions.json ] || echo "{}" > lan_sessions.json
[ -f ccos_cookie_cache.json ] || echo "{}" > ccos_cookie_cache.json
[ -f sapccheck/sapc_cookies.json ] || echo "[]" > sapccheck/sapc_cookies.json

# 2. Kiem tra file .env
if [ ! -f .env ]; then
    if [ -f .env.sample ]; then
        cp .env.sample .env
        echo "[INFO] Da tao file .env tu .env.sample"
    else
        touch .env
    fi
fi

# 3. Kiem tra load image neu co file tar
if [ -f pakh_precheck_image.tar ]; then
    echo "[INFO] Phat hien pakh_precheck_image.tar, dang nap vao Docker..."
    docker load -i pakh_precheck_image.tar
fi

# 4. Khoi dong container
echo "[INFO] Dang khoi chay container qua Docker Compose..."
docker compose up -d

echo "=================================================================="
echo " PAKH Precheck Web Dashboard dang chay tai: http://localhost:1234"
echo " Xem log: docker compose logs -f"
echo "=================================================================="
