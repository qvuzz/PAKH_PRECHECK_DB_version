# services/tts_new_data.py
# Nghiệp vụ: Hệ thống TTS Mới - Mobile Internet (REST API 1.000 phiếu)

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

def execute_tts_new_data_cycle():
    """
    Quy trình tiền kiểm tra phiếu sự cố từ hệ thống TTS Mới qua REST API:
    1. Gọi REST API lấy 1.000 phiếu đang xử lý.
    2. Lọc riêng các phiếu Mobile Internet (Data).
    3. Lấy số điện thoại thuê bao song song.
    4. Tra cứu Core: SAPC, CEM, BTools.
    5. Chạy Scenarios Engine & AI Summarizer để đưa ra nhận định, ý kiến và hướng xử lý.
    6. Lưu vào Database SQLite với source='tts_new' và xuất Excel báo cáo.
    7. TUYỆT ĐỐI KHÔNG TỰ ĐỘNG ĐÓNG PHIẾU (Chỉ tiền kiểm & hiển thị).
    """
    if state.status == "PROCESSING":
        state.log("WARN", "Hệ thống đang bận thực hiện chu kỳ khác.")
        return

    state.status = "PROCESSING"
    state.status_message = "Đang chạy tiền kiểm TTS Mới (REST API)..."
    state.current_step = "Kết nối REST API TTS Mới"

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from crawler_btools import extract_btools_single_phone
        from data_processor import standardize_btools_data
        from report_bot import (
            analyze_subscriber_status, 
            get_formatted_sapc_packages, 
            export_diagnostics_to_excel,
            extract_incident_time
        )
        from cem_client import CEMClient, save_cem_data_to_file

        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from converter import convert_sapc_response
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from ai_interpreter import analyze_ticket_with_ai

        from ttsnew_api import get_ttsnew_tickets_for_precheck
        state.log("STEP", "Đang kết nối REST API TTS Mới (gw-oneoss.vnpt.vn)...")

        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            state.log("ERROR", f"Không thể kết nối tới Chrome cổng 9222: {e}")
            return

        enriched_tickets, total_scanned = get_ttsnew_tickets_for_precheck(driver=driver)
        if not enriched_tickets:
            state.log("WARN", f"Đã quét {total_scanned} phiếu trên TTS Mới nhưng không tìm thấy phiếu Mobile Internet nào đang xử lý.")
            return

        total_tickets = len(enriched_tickets)
        state.log("SUCCESS", f"Thu được {total_tickets} thuê bao Mobile Internet từ TTS Mới (Tổng {total_scanned} phiếu). Bắt đầu tra cứu Core...")

        # Đồng bộ danh sách phiếu hiện hữu với thực tế trên REST API TTS Mới
        active_codes = {str(t.get("ticket_code", "")).strip() for t in enriched_tickets if t.get("ticket_code")}
        if active_codes:
            from db_manager import sync_active_tickets_state
            sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code")

        now = datetime.now()
        start_d = (now - timedelta(days=4)).strftime("%d%m%Y")
        end_d = now.strftime("%d%m%Y")

        # Khởi tạo SAPC & CEM
        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception as ex_s:
            state.log("WARN", f"Chưa khởi tạo được SAPCClient: {ex_s}")
            sapc_client = None

        try:
            cem_client = CEMClient(driver=driver)
        except Exception as ex_c:
            state.log("WARN", f"Chưa khởi tạo được CEMClient: {ex_c}")
            cem_client = None

        excel_summary_list = []

        for idx, ticket in enumerate(enriched_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng trong khi đang xử lý các thuê bao TTS Mới.")
                break

            phone_84 = normalize_phone_vn(ticket["phone"])
            title = str(ticket.get("title", "")).strip()
            content = str(ticket.get("content", "")).strip()
            ticket_code = str(ticket.get("ticket_code", "")).strip()
            incident_time_str = str(ticket.get("incident_time", "")).strip()
            created_time_str = str(ticket.get("created_time", "")).strip()

            state.current_step = f"Tra cứu thuê bao {idx}/{total_tickets}: {phone_84}"
            state.log("INFO", f"[{idx}/{total_tickets}] Đang tra cứu thuê bao: {phone_84} ({ticket_code} - {title})")

            # Tra cứu BTools (chạy ngầm tự động)
            raw_btools_data = extract_btools_single_phone(driver, phone_84, start_d, end_d)
            clean_data = standardize_btools_data(raw_btools_data)

            # Lưu file JSON vào number/
            output_dir = str(BASE_DIR / "number")
            os.makedirs(output_dir, exist_ok=True)
            json_filename = os.path.join(output_dir, f"{phone_84}.json")
            with open(json_filename, "w", encoding="utf-8") as jf:
                json.dump({
                    "phone": phone_84,
                    "package_title": title,
                    "ticket_content": content,
                    "title": title,
                    "content": content,
                    "ticket_code": ticket_code,
                    "btools_technical_data": clean_data if clean_data is not None else [],
                    "data": clean_data
                }, jf, ensure_ascii=False, indent=2)

            # Tra SAPC + HSS Profile
            if sapc_client is not None:
                try:
                    raw_sapc_data = sapc_client.query(phone_84)
                    sapc_result = convert_sapc_response(raw_sapc_data)
                except Exception as e:
                    sapc_result = {"msisdn": phone_84, "packages": []}

                info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session)
                hss_output_dir = str(BASE_DIR / "output")
                os.makedirs(hss_output_dir, exist_ok=True)
                with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                    json.dump({
                        **sapc_result,
                        "subscriber_info": info_result,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, hf, ensure_ascii=False, indent=4)

            # Tra cứu CEM & App Usage
            cem_records = []
            app_events = []
            cem_data_str = "Không có dữ liệu CEM"
            app_usage_str = "Không có dữ liệu App Usage"

            try:
                if cem_client is None:
                    cem_client = CEMClient(driver=driver)
                cem_records = cem_client.get_subscriber_history_5days(phone_84, days=5)
                cem_data_str = CEMClient.extract_top_cells_summary(cem_records)
                app_events = cem_client.get_subscriber_app_events(phone_84, days=5)
                app_usage_str = CEMClient.extract_top_apps_summary(app_events)

                save_cem_data_to_file(phone_84, cem_records, app_events, base_dir=BASE_DIR)
            except Exception as ex_cem:
                cem_data_str = f"Lỗi CEM: {ex_cem}"

            # Tóm tắt thông tin bằng AI / NLP Offline
            ai_summary = analyze_ticket_with_ai(json_filename)

            # Phân tích kịch bản
            status, comment, action_plan, color = analyze_subscriber_status(
                clean_data, title, content, phone_84=phone_84, cem_records=cem_records, app_events=app_events, incident_time_str=incident_time_str
            )
            state.log("INFO", f"   ↳ Nhận định: [{status}]")

            # Hạ tầng
            rats = list(set(str(r.get("RAT_TYPE_NAME", "")) for r in (clean_data or []) if r.get("RAT_TYPE_NAME")))
            rat_types_string = ", ".join(rats) if rats else "Không có dữ liệu"

            # Gói cước BTools / SAPC
            cfg_p = BASE_DIR / "diagnostic_config.json"
            ex_codes = set()
            if cfg_p.exists():
                with open(cfg_p, "r", encoding="utf-8") as cf:
                    ex_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
            real_pkgs = set()
            for r in (clean_data or []):
                sc = str(r.get("SERVICE_ID_CODE", "")).strip()
                sn = str(r.get("SERVICE_NAME", "")).strip()
                if sc.lower() and sc.lower() not in ex_codes:
                    if sn and "gói cước lạ" not in sn.lower() and sn.lower() not in ex_codes:
                        real_pkgs.add(sn)
                    else:
                        real_pkgs.add(sc)
            real_pkgs_str = ", ".join(list(real_pkgs)) if real_pkgs else "Không phát sinh gói TM"
            final_packages_str = get_formatted_sapc_packages(phone_84, fallback_btools=real_pkgs_str)

            rec = {
                "phone": phone_84,
                "ticket_code": ticket_code,
                "ticket_id": ticket.get("ticket_id"),
                "flow_id": ticket.get("flow_id"),
                "package_title": title,
                "incident_time": incident_time_str,
                "ticket_content": content,
                "created_time": created_time_str,
                "real_packages": final_packages_str,
                "rat_types": rat_types_string,
                "cem_data": cem_data_str,
                "app_usage": app_usage_str,
                "status": status,
                "comment": comment,
                "action_plan": action_plan,
                "color": color,
                "ticket_status": "Chưa đóng",
                "force_update_status": True,
                "source": "tts_new",
                "ai_summary": ai_summary if ai_summary else "null"
            }
            excel_summary_list.append(rec)
            save_or_update_ticket(rec)

        # Xuất file Excel báo cáo riêng cho TTS Mới
        if excel_summary_list:
            result_dir = BASE_DIR / "result"
            os.makedirs(result_dir, exist_ok=True)
            excel_name = result_dir / f"BaoCao_TienKiem_TTS_NEW_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
            saved_excel_file = export_diagnostics_to_excel(excel_summary_list, excel_name, start_d, end_d)
            state.log("SUCCESS", f"Báo cáo Excel TTS Mới đã lưu: {saved_excel_file}")

        state.log("SUCCESS", f"✅ Hoàn tất tiền kiểm tra {len(excel_summary_list)} phiếu TTS Mới. Dữ liệu đã hiển thị trên Dashboard (Chế độ chỉ hiển thị, không đóng phiếu).")

    except Exception as e:
        state.log("ERROR", f"Lỗi trong chu kỳ tiền kiểm TTS Mới: {e}")
    finally:
        state.status = "IDLE"
        state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."
        state.current_step = "Hoàn tất tiền kiểm TTS Mới"




# Alias tương thích
execute_ttsnew_cycle = execute_tts_new_data_cycle
