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
        self.status_message = "Hệ thống tự động tiền kiểm đang hoạt động"
        self.interval_minutes = 2.5  # Chu kỳ quét chuyên sâu nền tự động (BTools + SAPC)
        self.auto_close = False  # Mặc định KHÔNG tự đóng để đảm bảo an toàn, KTV phải chủ động bật & xác nhận 2 lần
        self.auto_close_tts_old = False  # TTS Cũ đã bỏ
        self.auto_close_tts_new = False  # Trạng thái tự đóng TTS Mới
        self.scan_scopes = ["tts_new_data", "tts_new_call", "tts_new_sms", "tts_new_other"]  # Quét tự động toàn bộ phân hệ TTS Mới
        self.auto_close_mode = "none"  # 'tts_new', 'none'
        self.ai_summary_engine = "qwen"  # 'qwen' (Qwen 2.5 GGUF) hoặc 'regex' (Regex thuần)
        self.engine = "tts_new"  # Hệ thống TTS Mới
        self.dry_run = False
        self.observe = False
        self.open_excel = False

        # Thống kê
        self.total_cycles = 0
        self.total_scanned = 0
        self.total_closed = 0
        self.closed_count = 0
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

    def clear_logs(self):
        with self.lock:
            self.logs = []

    def should_auto_close(self, source: str) -> bool:
        """
        Kiểm tra xem nguồn phiếu (source: 'tts_old' hoặc 'tts_new') có được phép tự động đóng hay không.
        """
        norm_source = "tts_old" if "old" in str(source).lower() else "tts_new"
        if norm_source == "tts_old":
            return bool(getattr(self, "auto_close_tts_old", False))
        elif norm_source == "tts_new":
            return bool(getattr(self, "auto_close_tts_new", False))
        return False

    def set_auto_close_for_system(self, system: str, enabled: bool):
        """
        Bật/tắt tự động đóng riêng biệt cho từng hệ thống (TTS Cũ hoặc TTS Mới)
        """
        with self.lock:
            s_low = str(system).lower()
            if "old" in s_low:
                self.auto_close_tts_old = bool(enabled)
            elif "new" in s_low:
                self.auto_close_tts_new = bool(enabled)

            if self.auto_close_tts_old and self.auto_close_tts_new:
                self.auto_close_mode = "all"
                self.auto_close = True
            elif self.auto_close_tts_old and not self.auto_close_tts_new:
                self.auto_close_mode = "tts_old"
                self.auto_close = True
            elif not self.auto_close_tts_old and self.auto_close_tts_new:
                self.auto_close_mode = "tts_new"
                self.auto_close = True
            else:
                self.auto_close_mode = "none"
                self.auto_close = False

    def set_auto_close_mode(self, mode: str):
        """
        Cập nhật chế độ đóng phiếu từ chuỗi mode ('all', 'tts_old', 'tts_new', 'none')
        """
        with self.lock:
            m = str(mode or "none").strip().lower()
            self.auto_close_mode = m
            if m == "all":
                self.auto_close_tts_old = True
                self.auto_close_tts_new = True
                self.auto_close = True
            elif m in ("tts_old", "old"):
                self.auto_close_tts_old = True
                self.auto_close_tts_new = False
                self.auto_close = True
            elif m in ("tts_new", "new"):
                self.auto_close_tts_old = False
                self.auto_close_tts_new = True
                self.auto_close = True
            else:
                self.auto_close_tts_old = False
                self.auto_close_tts_new = False
                self.auto_close = False

    def get_snapshot(self):
        with self.lock:
            return {
                "is_running": self.is_running,
                "status": self.status,
                "status_message": self.status_message,
                "interval_minutes": self.interval_minutes,
                "auto_close": self.auto_close,
                "auto_close_mode": getattr(self, "auto_close_mode", "none"),
                "auto_close_tts_old": False,
                "auto_close_tts_new": self.should_auto_close("tts_new"),
                "ai_summary_engine": getattr(self, "ai_summary_engine", "qwen"),
                "scan_scopes": list(getattr(self, "scan_scopes", ["tts_new_data", "tts_new_call", "tts_new_sms", "tts_new_other"])),
                "engine": getattr(self, "engine", "tts_new"),
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
