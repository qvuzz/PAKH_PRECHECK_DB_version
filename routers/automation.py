# routers/automation.py
# Quản lý tiến trình quét tự động, chu kỳ tiền kiểm và trạng thái hệ thống

import threading
from fastapi import APIRouter, Request
from services.state import state
from db_manager import get_system_counts
from services.tts_old_api_data import execute_tts_old_api_data_cycle
from services.tts_old_api_voice import execute_tts_old_api_voice_cycle
from services.tts_new_data import execute_tts_new_data_cycle
from services.tts_new_voice import execute_tts_new_voice_cycle

router = APIRouter(prefix="/api", tags=["Điều khiển Quét & Tự động hóa"])


@router.get("/status")
def get_system_status():
    snap = state.get_snapshot()
    snap["system_counts"] = get_system_counts()
    return snap


def is_admin_ip(client_ip: str) -> bool:
    if not client_ip:
        return True
    return client_ip in ("127.0.0.1", "localhost", "::1") or client_ip.startswith("127.")


@router.post("/start")
async def start_automation(request: Request):
    body = await request.json()
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = is_admin_ip(client_ip)

    state.is_running = True
    state.stop_requested = False
    state.trigger_now_requested = True
    if "scan_scopes" in body:
        state.scan_scopes = list(body["scan_scopes"])
    if not is_local:
        state.auto_close = False
        state.auto_close_mode = "none"
        if body.get("auto_close") or (body.get("auto_close_mode") and body.get("auto_close_mode") != "none"):
            state.log("WARNING", f"⛔ Đã chặn yêu cầu Tự đóng từ IP máy trạm {client_ip} (Chỉ Admin từ 127./localhost mới được phép)")
    elif "auto_close_mode" in body:
        state.auto_close_mode = str(body["auto_close_mode"]).strip()
        state.auto_close = (state.auto_close_mode != "none")
    elif "auto_close" in body:
        state.auto_close = bool(body["auto_close"])
        state.auto_close_mode = "all" if state.auto_close else "none"

    if "interval_minutes" in body:
        state.interval_minutes = int(body["interval_minutes"])

    engine = body.get("engine", getattr(state, "engine", "api"))
    state.engine = engine

    state.status_message = "Đang bắt đầu quét ngay lập tức..."
    state.log("INFO", f"🚀 BẮT ĐẦU QUÉT NGAY LẬP TỨC! Phạm vi: {state.scan_scopes} | Chế độ đóng phiếu: [{state.auto_close_mode}] | Lặp: {state.interval_minutes} phút | Client: {client_ip}")
    return {"success": True, "scan_scopes": state.scan_scopes, "auto_close_mode": state.auto_close_mode, "auto_close": state.auto_close}


@router.post("/config")
async def update_automation_config(request: Request):
    body = await request.json()
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = is_admin_ip(client_ip)

    if "scan_scopes" in body:
        state.scan_scopes = list(body["scan_scopes"])
        state.log("INFO", f"⚙️ Đã cập nhật phạm vi quét: {state.scan_scopes}")
    if not is_local:
        state.auto_close = False
        state.auto_close_mode = "none"
        if body.get("auto_close") or (body.get("auto_close_mode") and body.get("auto_close_mode") != "none"):
            state.log("WARNING", f"⛔ Đã chặn yêu cầu Tự đóng từ IP máy trạm {client_ip} (Chỉ Admin từ 127./localhost mới được phép)")
    elif "auto_close_mode" in body:
        state.auto_close_mode = str(body["auto_close_mode"]).strip()
        state.auto_close = (state.auto_close_mode != "none")
        state.log("INFO", f"⚙️ Đã chuyển chế độ đóng phiếu: [{state.auto_close_mode}]")
    elif "auto_close" in body:
        state.auto_close = bool(body["auto_close"])
        state.auto_close_mode = "all" if state.auto_close else "none"
    if "dry_run" in body:
        state.dry_run = bool(body["dry_run"])
    if "interval_minutes" in body:
        state.interval_minutes = int(body["interval_minutes"])

    return {"success": True, "scan_scopes": getattr(state, "scan_scopes", []), "auto_close_mode": getattr(state, "auto_close_mode", "none"), "auto_close": state.auto_close}


@router.post("/stop")
def stop_automation():
    state.stop_requested = True
    state.is_running = False
    state.log("WARN", "⏹️ DỪNG TIẾN TRÌNH QUÉT.")
    return {"success": True}


@router.post("/run-now")
async def trigger_run_now(request: Request):
    body = await request.json()
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")

    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}

    scopes = body.get("scan_scopes") or getattr(state, "scan_scopes", ["tts_old_data", "tts_new_data"])
    if not scopes:
        scopes = ["tts_old_data"]
    if not is_local:
        state.auto_close = False
        state.auto_close_mode = "none"
    elif "auto_close_mode" in body:
        state.auto_close_mode = str(body["auto_close_mode"]).strip()
        state.auto_close = (state.auto_close_mode != "none")
    elif "auto_close" in body:
        state.auto_close = bool(body["auto_close"])
        state.auto_close_mode = "all" if state.auto_close else "none"

    if state.is_running:
        state.trigger_now_requested = True
        state.log("INFO", f"⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC! (Phạm vi: {', '.join(scopes)})")
        return {"success": True}
    else:
        def _run_scopes_manual(sc_list):
            state.status = "PROCESSING"
            state.status_message = "Đang quét các phạm vi theo yêu cầu..."
            try:
                for sc in sc_list:
                    if state.stop_requested:
                        break
                    if sc == "tts_old_data":
                        execute_tts_old_api_data_cycle()
                    elif sc == "tts_old_voice":
                        execute_tts_old_api_voice_cycle()
                    elif sc == "tts_new_data":
                        execute_tts_new_data_cycle()
                    elif sc in ("tts_new_call", "tts_new_voice_call"):
                        from services.tts_new_voice import execute_tts_new_call_cycle
                        execute_tts_new_call_cycle()
                    elif sc == "tts_new_sms":
                        from services.tts_new_voice import execute_tts_new_sms_cycle
                        execute_tts_new_sms_cycle()
                    elif sc == "tts_new_other":
                        from services.tts_new_voice import execute_tts_new_other_cycle
                        execute_tts_new_other_cycle()
                    elif sc == "tts_new_voice":
                        execute_tts_new_voice_cycle()
            except Exception as ex_m:
                state.log("ERROR", f"Lỗi thực thi quét theo yêu cầu: {ex_m}")
            finally:
                state.status = "IDLE"
                state.status_message = "Hoàn tất quét theo yêu cầu."

        threading.Thread(target=_run_scopes_manual, args=(scopes,), daemon=True).start()
        return {"success": True, "message": "Đã kích hoạt quét ngay các phạm vi đã chọn."}


@router.post("/tts_old/scan_voice")
@router.post("/tts_old_api/scan_voice")
def scan_tts_old_voice():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    threading.Thread(target=execute_tts_old_api_voice_cycle, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét riêng phiếu Thoại / SMS từ TTS Cũ..."}


@router.post("/tts_old_api/run-now")
def run_now_tts_old_api():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    state.engine = "api"
    if state.is_running:
        state.trigger_now_requested = True
        state.log("INFO", "⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC (TTS CŨ - DATA)!")
        return {"success": True, "message": "Đã kích hoạt quét ngay chu kỳ mới!"}
    else:
        threading.Thread(target=execute_tts_old_api_data_cycle, daemon=True).start()
        return {"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Cũ (Data)..."}


@router.post("/ttsnew/run-now")
def run_now_tts_new():
    state.engine = "tts_new"
    from services.tts_new_data import execute_tts_new_data_cycle
    threading.Thread(target=execute_tts_new_data_cycle, daemon=True).start()
    return {"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Mới..."}


@router.post("/ttsnew/scan_call")
def scan_tts_new_call():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    from services.tts_new_voice import execute_tts_new_call_cycle
    threading.Thread(target=execute_tts_new_call_cycle, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Cuộc gọi từ TTS Mới..."}


@router.post("/ttsnew/scan_sms")
def scan_tts_new_sms():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    from services.tts_new_voice import execute_tts_new_sms_cycle
    threading.Thread(target=execute_tts_new_sms_cycle, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Tin nhắn từ TTS Mới..."}


@router.post("/ttsnew/scan_other")
def scan_tts_new_other():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    from services.tts_new_voice import execute_tts_new_other_cycle
    threading.Thread(target=execute_tts_new_other_cycle, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Gói cước & PA Khác từ TTS Mới..."}


@router.post("/ttsnew/scan_voice")
def scan_tts_new_voice():
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    threading.Thread(target=execute_tts_new_voice_cycle, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Thoại / SMS từ TTS Mới..."}


@router.get("/logs/clear")
@router.post("/logs/clear")
def clear_system_logs():
    state.clear_logs()
    return {"success": True, "message": "Đã xóa toàn bộ nhật ký"}
