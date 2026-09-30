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
        if body.get("auto_close") or (body.get("auto_close_mode") and body.get("auto_close_mode") != "none") or body.get("system"):
            state.log("WARNING", f"⛔ Đã chặn yêu cầu Tự đóng từ IP máy trạm {client_ip} (Chỉ Admin từ 127./localhost mới được phép)")
    elif "system" in body and "auto_close" in body:
        state.set_auto_close_for_system(str(body["system"]).strip(), bool(body["auto_close"]))
    elif "auto_close_mode" in body:
        state.set_auto_close_mode(str(body["auto_close_mode"]).strip())
    elif "auto_close" in body:
        state.set_auto_close_mode("all" if body["auto_close"] else "none")

    if "interval_minutes" in body:
        state.interval_minutes = int(body["interval_minutes"])

    engine = body.get("engine", getattr(state, "engine", "api"))
    state.engine = engine

    state.status_message = "Đang bắt đầu quét ngay lập tức..."
    state.log("INFO", f"🚀 BẮT ĐẦU QUÉT NGAY LẬP TỨC! Phạm vi: {state.scan_scopes} | Chế độ đóng phiếu: [{state.auto_close_mode}] | Lặp: {state.interval_minutes} phút | Client: {client_ip}")
    return {
        "success": True, 
        "scan_scopes": state.scan_scopes, 
        "auto_close_mode": state.auto_close_mode, 
        "auto_close": state.auto_close,
        "auto_close_tts_old": state.should_auto_close("tts_old"),
        "auto_close_tts_new": state.should_auto_close("tts_new")
    }


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
        if body.get("auto_close") or (body.get("auto_close_mode") and body.get("auto_close_mode") != "none") or body.get("auto_close_tts_old") or body.get("auto_close_tts_new") or body.get("system"):
            state.log("WARNING", f"⛔ Đã chặn yêu cầu Tự đóng từ IP máy trạm {client_ip} (Chỉ Admin từ 127./localhost mới được phép)")
    elif "system" in body and "auto_close" in body:
        sys_target = str(body["system"]).strip()
        state.set_auto_close_for_system(sys_target, bool(body["auto_close"]))
        state.log("INFO", f"⚙️ Đã cập nhật tự đóng [{sys_target}]: {body['auto_close']} -> Chế độ hiện tại: [{state.auto_close_mode}]")
    elif "auto_close_tts_old" in body or "auto_close_tts_new" in body:
        if "auto_close_tts_old" in body:
            state.set_auto_close_for_system("tts_old", bool(body["auto_close_tts_old"]))
        if "auto_close_tts_new" in body:
            state.set_auto_close_for_system("tts_new", bool(body["auto_close_tts_new"]))
        state.log("INFO", f"⚙️ Đã chuyển chế độ đóng phiếu: [{state.auto_close_mode}]")
    elif "auto_close_mode" in body:
        state.set_auto_close_mode(str(body["auto_close_mode"]).strip())
        state.log("INFO", f"⚙️ Đã chuyển chế độ đóng phiếu: [{state.auto_close_mode}]")
    elif "auto_close" in body:
        state.set_auto_close_mode("all" if body["auto_close"] else "none")
    if "dry_run" in body:
        state.dry_run = bool(body["dry_run"])
    if "interval_minutes" in body:
        state.interval_minutes = int(body["interval_minutes"])

    if "ai_summary_engine" in body:
        if not is_local:
            state.log("WARNING", f"⛔ Đã chặn thay đổi AI Summary Engine từ IP máy trạm {client_ip} (Chỉ Admin mới có quyền)")
        else:
            engine_val = str(body["ai_summary_engine"]).strip().lower()
            if engine_val in ("qwen", "regex"):
                state.ai_summary_engine = engine_val
                state.log("INFO", f"⚙️ Đã chuyển mô hình Tóm tắt nội dung sang: [{state.ai_summary_engine.upper()}]")

    return {
        "success": True, 
        "scan_scopes": getattr(state, "scan_scopes", []), 
        "auto_close_mode": getattr(state, "auto_close_mode", "none"), 
        "auto_close": state.auto_close,
        "auto_close_tts_old": state.should_auto_close("tts_old"),
        "auto_close_tts_new": state.should_auto_close("tts_new"),
        "ai_summary_engine": getattr(state, "ai_summary_engine", "qwen")
    }


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

    scopes = body.get("scan_scopes") or getattr(state, "scan_scopes", ["tts_old_data", "tts_old_voice", "tts_new_data", "tts_new_call", "tts_new_sms", "tts_new_other"])
    if not scopes:
        scopes = ["tts_old_data", "tts_old_voice"]
    if not is_local:
        state.auto_close = False
        state.auto_close_mode = "none"
    elif "system" in body and "auto_close" in body:
        state.set_auto_close_for_system(str(body["system"]).strip(), bool(body["auto_close"]))
    elif "auto_close_mode" in body:
        state.set_auto_close_mode(str(body["auto_close_mode"]).strip())
    elif "auto_close" in body:
        state.set_auto_close_mode("all" if body["auto_close"] else "none")

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
async def run_now_tts_old_api(request: Request = None):
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    state.engine = "api"
    force_recheck = False
    if request:
        try:
            body = await request.json()
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
        except Exception:
            pass

    threading.Thread(target=execute_tts_old_api_data_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Cũ (Data)..."}


@router.post("/ttsnew/run-now")
async def run_now_tts_new(request: Request):
    force_recheck = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
    except Exception:
        pass
    state.engine = "tts_new"
    from services.tts_new_data import execute_tts_new_data_cycle
    threading.Thread(target=execute_tts_new_data_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Mới..."}


@router.post("/ttsnew/scan_call")
async def scan_tts_new_call(request: Request):
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    force_recheck = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
    except Exception:
        pass
    from services.tts_new_voice import execute_tts_new_call_cycle
    threading.Thread(target=execute_tts_new_call_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Cuộc gọi từ TTS Mới..."}


@router.post("/ttsnew/scan_sms")
async def scan_tts_new_sms(request: Request):
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    force_recheck = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
    except Exception:
        pass
    from services.tts_new_voice import execute_tts_new_sms_cycle
    threading.Thread(target=execute_tts_new_sms_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Tin nhắn từ TTS Mới..."}


@router.post("/ttsnew/scan_other")
async def scan_tts_new_other(request: Request):
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    force_recheck = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
    except Exception:
        pass
    from services.tts_new_voice import execute_tts_new_other_cycle
    threading.Thread(target=execute_tts_new_other_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Gói cước & PA Khác từ TTS Mới..."}


@router.post("/ttsnew/scan_voice")
async def scan_tts_new_voice(request: Request):
    if state.status == "PROCESSING":
        return {"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."}
    force_recheck = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            force_recheck = bool(body.get("force") or body.get("force_recheck"))
    except Exception:
        pass
    from services.tts_new_voice import execute_tts_new_voice_cycle
    threading.Thread(target=execute_tts_new_voice_cycle, kwargs={"force_recheck": force_recheck}, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành quét phiếu Thoại / SMS từ TTS Mới..."}


@router.get("/logs/clear")
@router.post("/logs/clear")
def clear_system_logs():
    state.clear_logs()
    return {"success": True, "message": "Đã xóa toàn bộ nhật ký"}
