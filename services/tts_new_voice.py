# services/tts_new_voice.py
# Nghiệp vụ: Hệ thống TTS Mới - Thoại / SMS / Gói (Tiền kiểm On-Demand)

import os
import sys
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
    state.current_step = "Đang kết nối REST API TTS Mới để lấy phiếu Thoại / SMS"
    state.log("STEP", "⚡ Bắt đầu quét danh sách phiếu Thoại / SMS từ TTS Mới (REST API)...")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from ttsnew_api import get_ttsnew_tickets_for_precheck
        from db_manager import save_or_update_ticket, sync_active_tickets_state

        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)

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
            inc_time = str(t.get("incident_time") or t.get("created_time") or "")
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
                "source": "tts_new",
                "created_time": t.get("created_time", ""),
                "ticket_code": code,
                "flow_id": t.get("flow_id", "")
            }
            save_or_update_ticket(rec)

        if active_codes:
            sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code")

        state.log("INFO", f"✅ Đã nạp xong {len(voice_tickets)} phiếu lên bảng. Bạn có thể bấm [⚡ Tiền kiểm Core] trên từng phiếu để tiền kiểm thủ công hoặc để hệ thống tự động kiểm tra...")

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

        # Bước 2: Tuần tự tra cứu Core & Profile cho từng phiếu
        for idx, t in enumerate(voice_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng.")
                break

            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = t.get("ticket_code", "")

            state.current_step = f"Tiền kiểm tra thuê bao {idx}/{len(voice_tickets)}: {phone_84}"
            state.log("STEP", f"[{idx}/{len(voice_tickets)}] Đang tra cứu Core cho SĐT: {phone_84} ({code})...")

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

                hss_output_dir = str(BASE_DIR / "output")
                os.makedirs(hss_output_dir, exist_ok=True)
                with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                    json.dump({
                        **sapc_result,
                        "subscriber_info": info_result,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, hf, ensure_ascii=False, indent=4)

                formatted_packages = get_formatted_sapc_packages(phone_84)

                # Đối với Thoại / SMS / Gói: không gọi AI tóm tắt, chỉ dùng trực tiếp nội dung phản ánh
                ticket_content = t.get("content", "")

                cell_desc = info_result.get("Cell ID") or info_result.get("ECGI") or "--"
                rat_type_str = info_result.get("Radio") or "Sóng di động"

                # Đối với case không phải Mobile Internet: Nhận định, Cột 10, Cột 11 để trống
                rec_update = {
                    "phone": phone_84,
                    "incident_time": str(t.get("incident_time") or ""),
                    "package_title": t.get("title", "Thoại / SMS"),
                    "ticket_content": ticket_content,
                    "status": "",
                    "real_packages": formatted_packages,
                    "rat_types": rat_type_str,
                    "cem_data": f"Cell: {cell_desc}",
                    "app_usage": "--",
                    "ai_summary": ticket_content,
                    "comment": "",
                    "action_plan": "",
                    "ticket_status": "Chưa đóng",
                    "source": "tts_new",
                    "ticket_code": code,
                    "flow_id": t.get("flow_id", "")
                }
                save_or_update_ticket(rec_update)
                state.log("SUCCESS", f"[{idx}/{len(voice_tickets)}] Hoàn tất tra cứu Core cho {phone_84} ({code})")

            except Exception as e:
                state.log("ERROR", f"Lỗi xử lý {phone_84}: {e}")

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



