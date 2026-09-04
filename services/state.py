# services/state.py
# Quản lý trạng thái tiến trình, hàng đợi log và tiện ích chuẩn hóa số điện thoại

import threading
from datetime import datetime


def normalize_phone_vn(phone_raw: str) -> str:
    """
    Chuẩn hóa số điện thoại di động Việt Nam về định dạng chuẩn 84xxxxxxxxx (11 chữ số).
    Xử lý chuẩn xác trường hợp đầu số 084 (ví dụ 843651531 có 9 chữ số -> phải thành 84843651531).
    """
    clean = "".join(filter(str.isdigit, str(phone_raw or "").strip()))
    if not clean:
        return ""
    if clean.startswith("84") and len(clean) == 11:
        return clean
    if clean.startswith("0") and len(clean) == 10:
        return "84" + clean[1:]
    if len(clean) == 9:
        return "84" + clean
    if clean.startswith("0"):
        return "84" + clean[1:]
    if not clean.startswith("84"):
        return "84" + clean
    return clean


class AutomationState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.status = "IDLE"  # IDLE, PROCESSING, WAITING, STOPPING
        self.status_message = "Sẵn sàng khởi động"
        self.interval_minutes = 15  # Mặc định chu kỳ 15 phút
        self.auto_close = True
        self.engine = "api"  # 'api' (TTS Old REST API) hoặc 'selenium' (Chrome 9222)
        self.dry_run = False
        self.observe = False
        self.open_excel = False

        # Thống kê
        self.total_cycles = 0
        self.total_scanned = 0
        self.total_closed = 0
        self.last_run_time = None
        self.countdown_seconds = 0
        self.current_step = ""

        # Hàng đợi log
        self.logs = []
        self.max_logs = 300

        # Sự kiện ngắt chờ
        self.stop_requested = False
        self.trigger_now_requested = False

    def log(self, level, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": timestamp,
            "level": level.upper(),  # INFO, SUCCESS, WARN, ERROR, STEP
            "message": str(message)
        }
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
        # In ra terminal an toàn trên mọi hệ điều hành (tránh lỗi font cp1252 trên Windows)
        prefix = f"[{timestamp}] [{level.upper()}]"
        try:
            print(f"{prefix} {message}", flush=True)
        except Exception:
            try:
                print(f"{prefix} {str(message).encode('ascii', errors='replace').decode('ascii')}", flush=True)
            except Exception:
                pass

    def get_snapshot(self):
        with self.lock:
            return {
                "is_running": self.is_running,
                "status": self.status,
                "status_message": self.status_message,
                "interval_minutes": self.interval_minutes,
                "auto_close": self.auto_close,
                "engine": getattr(self, "engine", "api"),
                "dry_run": self.dry_run,
                "observe": self.observe,
                "open_excel": self.open_excel,
                "total_cycles": self.total_cycles,
                "total_scanned": self.total_scanned,
                "total_closed": self.total_closed,
                "last_run_time": self.last_run_time,
                "countdown_seconds": self.countdown_seconds,
                "current_step": self.current_step,
                "logs": list(self.logs)
            }


state = AutomationState()
