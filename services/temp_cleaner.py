# services/temp_cleaner.py
# Tự động dọn dẹp các file dữ liệu tạm/dump thô cũ hơn TTL (mặc định 1 ngày / 24 giờ).

import os
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIRS = ("cem", "number", "output", "result")
ALLOWED_EXTS = {".json", ".xlsx", ".xls", ".csv", ".log", ".tmp"}


def cleanup_old_temp_files(max_age_hours: float = 24.0, base_dir: Path = None) -> dict:
    """
    Xóa các file tạm có thời gian chỉnh sửa cũ hơn max_age_hours trong cem/, number/, output/, result/.
    Luôn giữ lại cấu trúc thư mục gốc và bỏ qua file mới hoặc đang được ghi.
    """
    root = Path(base_dir) if base_dir else BASE_DIR
    cutoff_ts = time.time() - (max_age_hours * 3600.0)
    removed_files = 0
    freed_bytes = 0

    for folder_name in TEMP_DIRS:
        folder_path = root / folder_name
        if not folder_path.is_dir():
            continue

        for dirpath, _, filenames in os.walk(folder_path):
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() not in ALLOWED_EXTS:
                    continue
                try:
                    stat = fpath.stat()
                    if stat.st_mtime < cutoff_ts:
                        fsize = stat.st_size
                        fpath.unlink()
                        removed_files += 1
                        freed_bytes += fsize
                except Exception:
                    continue

    return {
        "removed_files": removed_files,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
    }


def start_temp_cleaner_daemon(max_age_hours: float = 24.0, interval_hours: float = 6.0, initial_delay_sec: float = 30.0):
    """Khởi chạy luồng nền định kỳ dọn dẹp file tạm mỗi interval_hours giờ."""
    def _loop():
        time.sleep(initial_delay_sec)
        while True:
            try:
                res = cleanup_old_temp_files(max_age_hours=max_age_hours)
                if res["removed_files"] > 0:
                    print(
                        f"[TEMP CLEANER] Đã dọn {res['removed_files']} file tạm cũ > {int(max_age_hours)}h "
                        f"(giải phóng {res['freed_mb']} MB).",
                        flush=True,
                    )
            except Exception as ex:
                print(f"[TEMP CLEANER WARN] Lỗi dọn file tạm: {ex}", flush=True)
            time.sleep(interval_hours * 3600.0)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
