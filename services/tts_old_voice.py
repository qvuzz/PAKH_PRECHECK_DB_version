# services/tts_old_voice.py
# Nghiệp vụ: Hệ thống TTS Cũ - Thoại / SMS / Gói (Tiền kiểm On-Demand)

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from services.state import state, normalize_phone_vn
from db_manager import save_or_update_ticket, sync_active_tickets_state

def execute_tts_old_voice_cycle():
    state.status = "PROCESSING"
    state.status_message = "Đang quét phiếu Thoại / SMS..."
    state.current_step = "Đang kết nối Chrome để cào phiếu Thoại / SMS trên TTS Cũ"
    state.log("STEP", "⚡ Bắt đầu quét riêng danh sách phiếu Thoại / SMS từ TTS Cũ...")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from crawler_tts import get_vnpt_tickets
        from db_manager import save_or_update_ticket, sync_active_tickets_state

        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)

        raw_tickets, _ = get_vnpt_tickets(driver, service_type="voice_sms")
        if not raw_tickets:
            state.log("WARN", "ℹ️ Trên bảng TTS Cũ hiện tại không có phiếu Thoại / SMS / Gói cước nào (Toàn bộ là phiếu Mobile Internet).")
            return 0

        voice_tickets = raw_tickets
        state.log("SUCCESS", f"Thu được {len(voice_tickets)} phiếu Thoại / SMS từ bảng TTS Cũ. Đang nạp vào bảng...")

        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status

        # Bước 1: Nạp nhanh toàn bộ phiếu vào Database trước để người dùng thấy ngay trên bảng
        active_phones = set()
        for t in voice_tickets:
            phone = str(t.get("phone", "")).strip()
            phone_84 = normalize_phone_vn(phone)
            active_phones.add(phone_84)
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
                "source": "tts_old",
                "created_time": t.get("created_time", "")
            }
            save_or_update_ticket(rec)

        if active_phones:
            sync_active_tickets_state(active_phones, source="tts_old", key_type="phone")

        state.log("INFO", f"✅ Đã nạp xong {len(voice_tickets)} phiếu lên bảng. Bắt đầu tiền kiểm tra Core & AI chi tiết...")

        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            sapc_client = None

        # Bước 2: Tuần tự tra cứu Core & Profile cho từng phiếu
        for idx, t in enumerate(voice_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng.")
                break

            phone = str(t.get("phone", "")).strip()
            phone_84 = normalize_phone_vn(phone)

            state.current_step = f"Tiền kiểm tra thuê bao {idx}/{len(voice_tickets)}: {phone_84}"
            state.log("STEP", f"[{idx}/{len(voice_tickets)}] Đang tra cứu Core (HSS/HLR/Cell) cho SĐT: {phone_84}...")

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

                final_packages_str = get_formatted_sapc_packages(phone_84)

                # Đối với Thoại / SMS / Gói: không gọi AI tóm tắt, chỉ dùng trực tiếp nội dung phản ánh
                ticket_content = t.get("content", "")

                cell_desc = info_result.get("Cell ID") or info_result.get("ECGI") or "--"
                rat = info_result.get("Radio") or "Sóng di động"

                # Đối với case không phải Mobile Internet: Nhận định, Cột 10, Cột 11 để trống
                rec = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", "Thoại / SMS"),
                    "ticket_content": ticket_content,
                    "status": "",
                    "real_packages": final_packages_str,
                    "rat_types": rat,
                    "cem_data": f"Cell: {cell_desc}",
                    "app_usage": "--",
                    "ai_summary": ticket_content,
                    "comment": "",
                    "action_plan": "",
                    "ticket_status": "Chưa đóng",
                    "source": "tts_old",
                    "created_time": t.get("created_time", "")
                }
                save_or_update_ticket(rec)
            except Exception as ex_single:
                state.log("WARN", f"Lỗi xử lý tiền kiểm tra cho {phone_84}: {ex_single}")

        if active_phones:
            sync_active_tickets_state(active_phones, source="tts_old", key_type="phone")

        state.log("SUCCESS", f"✅ Đã tiền kiểm tra Core hoàn tất cho {len(voice_tickets)} phiếu Thoại / SMS!")
        return len(voice_tickets)

    except Exception as e:
        state.log("ERROR", f"Lỗi khi quét phiếu Thoại / SMS từ TTS Cũ: {e}")
        return 0
    finally:
        state.status = "IDLE"
        state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."
        state.current_step = "Sẵn sàng"


