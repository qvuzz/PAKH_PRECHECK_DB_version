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

def execute_ttsnew_voice_cycle():
    state.status = "PROCESSING"
    state.status_message = "Đang quét phiếu Thoại / SMS TTS Mới..."
    state.current_step = "Đang lấy danh sách phiếu Thoại / SMS TTS Mới"
    state.log("STEP", "⚡ Bắt đầu quét danh sách phiếu Thoại / SMS từ TTS Mới...")

    try:
        from ttsnew_api import get_ttsnew_tickets_for_precheck
        from db_manager import save_or_update_ticket, sync_active_tickets_state

        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        voice_tickets, total_scanned = get_ttsnew_tickets_for_precheck(driver=driver, service_type="voice_sms")
        if not voice_tickets:
            state.log("WARN", f"ℹ️ Đã quét {total_scanned} phiếu trên TTS Mới nhưng không có phiếu Thoại / SMS / Gói cước nào đang xử lý.")
            return 0

        state.log("SUCCESS", f"Thu được {len(voice_tickets)} phiếu Thoại / SMS từ TTS Mới (Tổng quét: {total_scanned}). Đang nạp vào bảng...")

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
            sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code", service_type="voice_sms")

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

        # Bước 2: Tra cứu Core & Profile song song để xử lý nhanh toàn bộ danh sách phiếu
        import concurrent.futures
        hss_output_dir = str(BASE_DIR / "output")
        os.makedirs(hss_output_dir, exist_ok=True)

        def _process_single_voice_ticket(item_tuple):
            idx, t = item_tuple
            if state.stop_requested:
                return False
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = t.get("ticket_code", "")
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()

            state.current_step = f"Tra cứu Core {idx}/{len(voice_tickets)}: {phone_84}"
            try:
                info_result = {}
                sapc_result = {"msisdn": phone_84, "packages": []}
                if sapc_client:
                    try:
                        info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session)
                        raw_sapc = sapc_client.query(phone_84)
                        sapc_result = convert_sapc_response(raw_sapc)
                    except Exception as ex_core:
                        state.log("WARN", f"Lỗi tra Core cho {phone_84}: {ex_core}")

                with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                    json.dump({
                        **sapc_result,
                        "subscriber_info": info_result,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, hf, ensure_ascii=False, indent=4)

                formatted_packages = get_formatted_sapc_packages(phone_84)

                ticket_content = t.get("content", "")
                reopen_count = int(t.get("reopen_count") or 0)
                last_reopened_date = str(t.get("last_reopened_date") or "").strip()

                ai_summary_val = ticket_content
                if reopen_count > 0:
                    warn_prefix = f"⚠️ [CẢNH BÁO: Phiếu mở lại {reopen_count} lần"
                    if last_reopened_date:
                        warn_prefix += f" (Lần cuối: {last_reopened_date})"
                    warn_prefix += " - Yêu cầu KTV kiểm tra kỹ!]\n"
                    ai_summary_val = warn_prefix + (ticket_content or "")
                    state.log("WARN", f"⚠️ Phiếu Thoại/SMS {code} ({phone_84}) mở lại {reopen_count} lần -> Cảnh báo KTV kiểm tra!")

                cell_desc = info_result.get("Cell ID") or info_result.get("ECGI") or "--"
                rat_type_str = info_result.get("Radio") or "Sóng di động"

                rec_update = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", "Thoại / SMS"),
                    "ticket_content": ticket_content,
                    "status": "",
                    "real_packages": formatted_packages,
                    "rat_types": rat_type_str,
                    "cem_data": f"Cell: {cell_desc}",
                    "app_usage": "--",
                    "ai_summary": ai_summary_val,
                    "comment": "",
                    "action_plan": "",
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
                state.log("SUCCESS", f"[{idx}/{len(voice_tickets)}] Đã tra cứu Core: {phone_84} ({code.split(chr(10))[0]})")
                return True
            except Exception as e:
                state.log("ERROR", f"Lỗi xử lý {phone_84}: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            items = list(enumerate(voice_tickets, 1))
            futures = [executor.submit(_process_single_voice_ticket, it) for it in items]
            for future in concurrent.futures.as_completed(futures):
                if state.stop_requested:
                    state.log("WARN", "Nhận được yêu cầu dừng.")
                    break

        state.log("SUCCESS", f"🎉 Hoàn tất chu kỳ tiền kiểm Thoại / SMS TTS Mới cho {len(voice_tickets)} phiếu.")
        return len(voice_tickets)

    except Exception as e:
        state.log("ERROR", f"Lỗi quét phiếu Thoại / SMS TTS Mới: {e}")
        return 0
    finally:
        state.status = "IDLE"
        state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."
        state.current_step = "Sẵn sàng"


# Alias tương thích
execute_tts_new_voice_cycle = execute_ttsnew_voice_cycle



