# services/automation_worker.py
# Luồng lặp tự động chạy ngầm theo chu kỳ thời gian (Background Worker Thread)

import time
from services.state import state
from services.tts_old_api_data import execute_tts_old_api_data_cycle

def automation_worker_loop():
    while True:
        if not state.is_running and not state.trigger_now_requested:
            state.status = "IDLE"
            state.status_message = "Đã dừng. Sẵn sàng nhận lệnh START."
            time.sleep(0.5)
            continue

        state.is_running = True
        state.trigger_now_requested = False

        # Thực thi chu kỳ tự động ngầm 100% bằng REST API siêu tốc (không kích hoạt code Selenium)
        execute_tts_old_api_data_cycle()

        if not state.is_running or state.stop_requested:
            state.is_running = False
            state.stop_requested = False
            state.status = "IDLE"
            state.status_message = "Đã dừng tiến trình tự động."
            continue

        # Nghỉ theo interval
        state.status = "WAITING"
        total_wait_secs = int(state.interval_minutes * 60)
        state.countdown_seconds = total_wait_secs

        state.log("INFO", f"⏳ Hoàn tất chu kỳ. Đang đếm ngược {state.interval_minutes} phút trước chu kỳ mới...")

        while state.countdown_seconds > 0 and state.is_running:
            max_allowed_secs = int(state.interval_minutes * 60)
            if state.countdown_seconds > max_allowed_secs:
                state.countdown_seconds = max_allowed_secs

            if state.stop_requested:
                state.is_running = False
                state.stop_requested = False
                state.log("WARN", "Đã nhận lệnh STOP trong lúc chờ. Dừng vòng lặp.")
                break

            if state.trigger_now_requested:
                state.trigger_now_requested = False
                state.log("INFO", "⚡ Kích hoạt chu kỳ ngay lập tức theo yêu cầu!")
                break

            mins, secs = divmod(state.countdown_seconds, 60)
            state.status_message = f"Đang chờ chu kỳ tiếp theo: {mins:02d}:{secs:02d}"
            time.sleep(1)
            state.countdown_seconds -= 1
