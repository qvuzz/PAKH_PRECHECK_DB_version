#!/bin/bash
# ==============================================================================
# Script Khoi Dong PAKH Precheck tren Linux Server
# ==============================================================================
set -e

echo "=== [PAKH PRECHECK] Dang chuan bi moi truong tren Server ==="

# 1. Tu dong phat hien va don dep cac thu muc rac do Docker tao nham neu truoc do thieu file
find . -maxdepth 1 -type d \( -name "*.py" -o -name "*.json" \) -exec rm -rf {} + 2>/dev/null || true

# 2. Tao cac thu muc can thiet
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

# 2. Tu dong chuan hoa phan vung theo Quy trinh OneOSS (SOC1=MB, SOC2=MN, SOC3=MT) va phuc hoi phieu MN bi dong nham
if [ -f tickets.db ] && command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 tickets.db "
        UPDATE tickets SET region = 'MN' WHERE instr(ticket_code, 'SOC2') > 0 OR instr(ticket_code, 'SOC 2') > 0;
        UPDATE tickets SET region = 'MT' WHERE instr(ticket_code, 'SOC3') > 0 OR instr(ticket_code, 'SOC 3') > 0;
        UPDATE tickets SET region = 'MB' WHERE instr(ticket_code, 'SOC1') > 0 OR instr(ticket_code, 'SOC 1') > 0;
        UPDATE tickets SET region = 'MN' WHERE (region IS NULL OR region = '' OR region = 'MB' OR region = 'MT') AND instr(ticket_code, 'SOC1') = 0 AND instr(ticket_code, 'SOC 1') = 0 AND instr(ticket_code, 'SOC3') = 0 AND instr(ticket_code, 'SOC 3') = 0;
        UPDATE tickets SET ticket_status = 'Chưa đóng' WHERE region = 'MN' AND (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') AND (closed_by IS NULL OR closed_by = '' OR closed_by = 'Kỹ thuật viên') AND updated_at LIKE '%$(date +%Y-%m-%d)%';
    " 2>/dev/null || true
fi

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
