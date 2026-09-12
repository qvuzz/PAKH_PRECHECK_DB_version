# dashboard.py
# Hệ Thống Tiền Kiểm Phản Ánh Khách Hàng (PAKH Precheck) - VNPT
# Web Dashboard Server (FastAPI + Uvicorn)

import os
import sys
import time
import socket
import threading
import subprocess
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
PORT = 1234

# Bảo vệ khi chạy ngầm bằng pythonw (tránh NoneType write error)
if sys.stdout is None:
    try:
        sys.stdout = open(BASE_DIR / "dashboard_service.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    try:
        sys.stderr = open(BASE_DIR / "dashboard_service.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w")

# Database & State Initialization
from db_manager import init_db
from services.state import state
from services.automation_worker import automation_worker_loop

# Modular Routers
from routers import web, auth, automation, tickets, integrations


# ==============================================================================
# TIỆN ÍCH QUẢN LÝ TIẾN TRÌNH VÀ TRÌNH DUYỆT CHROME DEBUG
# ==============================================================================
def kill_existing_port_process(port: int):
    """Đảm bảo không có tiến trình zombie cũ nào chiếm port trước khi bind."""
    try:
        current_pid = os.getpid()
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        for line in output.strip().splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = int(parts[-1])
                if pid != current_pid and pid > 0:
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        print(f"⚠️ Đã giải phóng tiến trình cũ (PID: {pid}) đang chiếm port {port}.")
                    except Exception:
                        pass
    except Exception:
        pass


def launch_chrome_debug():
    """Kiểm tra Chrome Debugging (port 9222) nếu có sẵn thì thông báo."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        if res == 0:
            print("✅ Chrome Debugging (Port 9222) đã sẵn sàng.")
            return True
    except Exception:
        pass
    return False


def open_in_chrome_debug(url: str):
    """Kích hoạt hoặc mở tab mới trong Chrome Debugging."""
    try:
        import requests
        tabs_res = requests.get("http://127.0.0.1:9222/json/list", timeout=0.5)
        if tabs_res.status_code == 200:
            tabs = tabs_res.json()
            for t in tabs:
                if f":{PORT}" in t.get("url", ""):
                    requests.get(f"http://127.0.0.1:9222/json/activate/{t.get('id')}", timeout=0.5)
                    return
            requests.get(f"http://127.0.0.1:9222/json/new?{url}", timeout=0.5)
            return
    except Exception:
        pass


# ==============================================================================
# LIFESPAN CONTEXT MANAGER
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo database SQLite
    init_db()
    launch_chrome_debug()

    # Khởi chạy luồng worker tự động quét ngầm
    worker_thread = threading.Thread(target=automation_worker_loop, daemon=True)
    worker_thread.start()

    # Mở tab trên Chrome Debug
    open_in_chrome_debug(f"http://localhost:{PORT}")

    yield

    state.stop_requested = True
    state.is_running = False


# ==============================================================================
# FASTAPI APPLICATION CREATION
# ==============================================================================
app = FastAPI(
    title="VNPT TTS Precheck Dashboard",
    description="Hệ thống Tiền Kiểm Phản Ánh Khách Hàng - VNPT VinaPhone",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Directory
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(auth.router)
app.include_router(automation.router)
app.include_router(tickets.router)
app.include_router(integrations.router)
app.include_router(web.router)


# ==============================================================================
# HÀM KHỞI CHẠY MÁY CHỦ WEB
# ==============================================================================
def run_dashboard():
    kill_existing_port_process(PORT)
    print("================================================================")
    print(f"[PAKH Precheck] FastAPI Web Dashboard dang chay tai: http://localhost:{PORT}")
    print(f"[PAKH Precheck] Tai lieu Swagger API: http://localhost:{PORT}/docs")
    print("================================================================")

    # Chạy Uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=False
    )


if __name__ == "__main__":
    run_dashboard()
