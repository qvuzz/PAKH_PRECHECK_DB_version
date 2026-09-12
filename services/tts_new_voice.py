# services/tts_new_voice.py
# Nghiệp vụ: Hệ thống TTS Mới - Thoại / SMS / Gói (Tiền kiểm On-Demand)

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from services.state import state, normalize_phone_vn
from db_manager import (
    save_or_update_ticket, 
    sync_active_tickets_state, 
    get_db_connection
)
import ttsnew_api

def execute_ttsnew_voice_cycle(service_type: str = "voice_sms"):
    type_labels = {
        "call": "Cuộc gọi",
        "sms": "Tin nhắn",
        "other": "Gói cước / PA Khác",
        "voice_sms": "Thoại / SMS / Gói"
    }
    lbl = type_labels.get(service_type, "Thoại / SMS")
    state.status = "PROCESSING"
    state.status_message = f"Đang quét phiếu {lbl} TTS Mới..."
    state.current_step = f"Đang lấy danh sách phiếu {lbl} TTS Mới"
    state.log("STEP", f"⚡ Bắt đầu quét danh sách phiếu {lbl} từ TTS Mới...")

    try:
        from ttsnew_api import get_ttsnew_tickets_for_precheck
        from db_manager import save_or_update_ticket, sync_active_tickets_state

        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        voice_tickets, total_scanned = get_ttsnew_tickets_for_precheck(driver=driver, service_type=service_type)
        if not voice_tickets:
            state.log("WARN", f"ℹ️ Đã quét {total_scanned} phiếu trên TTS Mới nhưng không có phiếu {lbl} nào đang xử lý.")
            return 0

        state.log("SUCCESS", f"Thu được {len(voice_tickets)} phiếu {lbl} từ TTS Mới (Tổng quét: {total_scanned}). Đang nạp vào bảng...")

        # Bước 1: Nạp nhanh toàn bộ phiếu vào Database trước với status CHỜ TIỀN KIỂM
        active_codes = set()
        for t in voice_tickets:
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = str(t.get("ticket_code", "")).strip()
            if code:
                active_codes.add(code)
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()
            rec = {
                "phone": phone_84,
                "incident_time": inc_time,
                "package_title": t.get("title", "Thoại / SMS"),
                "ticket_content": t.get("content", ""),
                "status": "CHỜ TIỀN KIỂM",
                "real_packages": "--",
                "rat_types": "--",
                "cem_data": "--",
                "app_usage": "--",
                "ai_summary": t.get("content", ""),
                "comment": "",
                "action_plan": "",
                "ticket_status": "Chưa đóng",
                "force_update_status": True,
                "source": "tts_new",
                "created_time": t.get("created_time", ""),
                "ticket_code": code,
                "ticket_id": t.get("ticket_id"),
                "flow_id": t.get("flow_id", ""),
                "reopen_count": int(t.get("reopen_count") or 0),
                "last_reopened_date": str(t.get("last_reopened_date") or "").strip()
            }
            save_or_update_ticket(rec)

        if active_codes:
            sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code", service_type=service_type)

        state.log("INFO", f"✅ Đã nạp xong {len(voice_tickets)} phiếu lên bảng. Đang tiến hành tra cứu Core...")

        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status

        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            sapc_client = None

        from cem_client import CEMClient
        try:
            cem_client = CEMClient()
        except Exception:
            cem_client = None

        from services.voice_precheck import precheck_single_voice_ticket

        # Bước 2: Tra cứu Core & Profile song song để xử lý nhanh toàn bộ danh sách phiếu
        import concurrent.futures

        def _process_single_voice_ticket(item_tuple):
            idx, t = item_tuple
            if state.stop_requested:
                return False
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = t.get("ticket_code", "")
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()

            state.current_step = f"Tiền kiểm {lbl} {idx}/{len(voice_tickets)}: {phone_84}"
            try:
                step_name_raw = str(t.get("step_name") or "")
                is_step_26 = ("2.6" in step_name_raw) or (t.get("ticket_status") == "Chờ đóng lần 2")

                existing_db_row = None
                try:
                    conn_chk = get_db_connection()
                    existing_db_row = conn_chk.execute("""
                        SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary
                        FROM tickets 
                        WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                        ORDER BY updated_at DESC LIMIT 1
                    """, (t.get("ticket_id"), f"{code}%", phone_84)).fetchone()
                    conn_chk.close()
                except Exception:
                    pass

                def _is_valid_technical_status(st):
                    if not st:
                        return False
                    s_u = str(st).strip().upper()
                    if "LỖI KẾT NỐI" in s_u or "CHƯA ĐĂNG NHẬP" in s_u or "LỖI MÁY CHỦ" in s_u or "CHƯA PHÂN LOẠI" in s_u or "CHỜ TIỀN KIỂM" in s_u:
                        return False
                    return True

                can_reuse_db = (
                    existing_db_row 
                    and existing_db_row["comment"] 
                    and _is_valid_technical_status(existing_db_row["status"])
                )

                if can_reuse_db:
                    state.log("INFO", f"   ↳ 📋 Thuê bao {phone_84} đã có kết quả tiền kiểm trong DB: [{existing_db_row['status']}]. Giữ nguyên hiển thị.")
                    eval_res = {
                        "status": existing_db_row["status"],
                        "color": existing_db_row["color"] or "green",
                        "comment": existing_db_row["comment"],
                        "action_plan": existing_db_row["action_plan"] or "Đủ điều kiện đóng phiếu",
                        "real_packages": existing_db_row["real_packages"] or "--",
                        "rat_types": existing_db_row["rat_types"] or "2G/3G/4G Thoại",
                        "cem_data": existing_db_row["cem_data"] or "--",
                        "ai_summary": existing_db_row["ai_summary"] or t.get("content", "")
                    }
                else:
                    eval_res = precheck_single_voice_ticket(
                        phone_84=phone_84, 
                        ticket=t, 
                        sapc_client=sapc_client, 
                        cem_client=cem_client
                    )

                ticket_content = t.get("content", "")
                reopen_count = int(t.get("reopen_count") or 0)
                last_reopened_date = str(t.get("last_reopened_date") or "").strip()

                rec_update = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", "Cuộc gọi"),
                    "ticket_content": ticket_content,
                    "status": eval_res.get("status", "MẠNG LƯỚI ĐẢM BẢO"),
                    "color": eval_res.get("color", "green"),
                    "comment": eval_res.get("comment", ""),
                    "action_plan": eval_res.get("action_plan", "Đủ điều kiện đóng phiếu"),
                    "real_packages": eval_res.get("real_packages", "--"),
                    "rat_types": eval_res.get("rat_types", "2G/3G/4G Thoại"),
                    "cem_data": eval_res.get("cem_data", "--"),
                    "app_usage": "--",
                    "ai_summary": eval_res.get("ai_summary", ticket_content),
                    "ticket_status": "Chưa đóng",
                    "force_update_status": True,
                    "source": "tts_new",
                    "ticket_code": code,
                    "ticket_id": t.get("ticket_id"),
                    "flow_id": t.get("flow_id", ""),
                    "reopen_count": reopen_count,
                    "last_reopened_date": last_reopened_date
                }
                save_or_update_ticket(rec_update)
                state.log("SUCCESS", f"[{idx}/{len(voice_tickets)}] Đã tiền kiểm Cuộc gọi: {phone_84} -> {eval_res.get('status')}")
                return True
            except Exception as e:
                state.log("ERROR", f"Lỗi tiền kiểm {phone_84}: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            items = list(enumerate(voice_tickets, 1))
            futures = [executor.submit(_process_single_voice_ticket, it) for it in items]
            for future in concurrent.futures.as_completed(futures):
                if state.stop_requested:
                    state.log("WARN", "Nhận được yêu cầu dừng.")
                    break

        state.log("SUCCESS", f"🎉 Hoàn tất chu kỳ tiền kiểm {lbl} TTS Mới cho {len(voice_tickets)} phiếu.")
        return len(voice_tickets)

    except Exception as e:
        state.log("ERROR", f"Lỗi quét phiếu {lbl} TTS Mới: {e}")
        return 0
    finally:
        state.status = "IDLE"
        state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."
        state.current_step = "Sẵn sàng"


# Alias & Helper cycles cho từng module
execute_tts_new_voice_cycle = execute_ttsnew_voice_cycle

def execute_tts_new_call_cycle():
    return execute_ttsnew_voice_cycle(service_type="call")

def execute_tts_new_sms_cycle():
    return execute_ttsnew_voice_cycle(service_type="sms")

def execute_tts_new_other_cycle():
    return execute_ttsnew_voice_cycle(service_type="other")



