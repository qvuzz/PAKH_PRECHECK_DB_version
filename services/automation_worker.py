# services/automation_worker.py
# Luồng lặp tự động chạy ngầm theo chu kỳ thời gian (Background Worker Thread)

import time
from services.state import state
from services.tts_old_api_data import execute_tts_old_api_data_cycle

def automation_worker_loop():
    while True:
        if not state.is_running and not state.trigger_now_requested:
            if state.status != "PROCESSING":
                state.status = "IDLE"
                state.status_message = "Đã dừng. Sẵn sàng nhận lệnh START."
            time.sleep(0.5)
            continue

        state.is_running = True
        state.trigger_now_requested = False

        # Thực thi chu kỳ tự động ngầm theo danh sách phạm vi (scan_scopes) đã chọn
        scopes = getattr(state, "scan_scopes", ["tts_old_data", "tts_new_data"])
        if not scopes:
            scopes = ["tts_old_data"]

        state.log("INFO", f"🔄 Bắt đầu chu kỳ quét tự động. Phạm vi: {', '.join(scopes)}")

        for sc in scopes:
            if not state.is_running or state.stop_requested:
                break
            try:
                if sc == "tts_old_data":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS CŨ - MOBILE INTERNET ---")
                    execute_tts_old_api_data_cycle()
                elif sc == "tts_old_voice":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS CŨ - THOẠI / SMS / GÓI ---")
                    from services.tts_old_api_voice import execute_tts_old_api_voice_cycle
                    execute_tts_old_api_voice_cycle()
                elif sc == "tts_new_data":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS MỚI - MOBILE INTERNET ---")
                    from services.tts_new_data import execute_tts_new_data_cycle
                    execute_tts_new_data_cycle()
                elif sc in ("tts_new_call", "tts_new_voice_call"):
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS MỚI - CUỘC GỌI ---")
                    from services.tts_new_voice import execute_tts_new_call_cycle
                    execute_tts_new_call_cycle()
                elif sc == "tts_new_sms":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS MỚI - TIN NHẮN ---")
                    from services.tts_new_voice import execute_tts_new_sms_cycle
                    execute_tts_new_sms_cycle()
                elif sc == "tts_new_other":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS MỚI - GÓI CƯỚC / PA KHÁC ---")
                    from services.tts_new_voice import execute_tts_new_other_cycle
                    execute_tts_new_other_cycle()
                elif sc == "tts_new_voice":
                    state.log("STEP", "--- BẮT ĐẦU QUÉT: TTS MỚI - THOẠI / SMS / GÓI ---")
                    from services.tts_new_voice import execute_tts_new_voice_cycle
                    execute_tts_new_voice_cycle()
            except Exception as e:
                state.log("ERROR", f"Lỗi khi thực thi quét phạm vi {sc}: {e}")

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
