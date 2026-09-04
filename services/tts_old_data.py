# services/tts_old_data.py
# Nghiệp vụ: Hệ thống TTS Cũ - Mobile Internet (Quét & Đóng tự động)

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
    check_ticket_can_close, 
    update_ticket_field, 
    sync_active_tickets_state
)

def execute_tts_old_data_cycle():
    state.status = "PROCESSING"
    state.current_step = "Đang kết nối Chrome Port 9222..."
    state.log("STEP", "Bắt đầu chu kỳ quét và tiền kiểm PAKH...")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from crawler_tts import get_vnpt_tickets
        from crawler_btools import extract_btools_single_phone
        from data_processor import standardize_btools_data
        from report_bot import (
            analyze_subscriber_status, 
            get_formatted_sapc_packages, 
            export_diagnostics_to_excel,
            extract_incident_time
        )
        from cem_client import CEMClient, save_cem_data_to_file
        from ai_interpreter import analyze_ticket_with_ai

        # Module SAPC
        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from converter import convert_sapc_response
        from msisdn_info import tra_cell_tu_so_dien_thoai

        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            state.log("ERROR", f"Không thể kết nối tới Chrome cổng 9222: {e}")
            state.log("WARN", "Hãy chắc chắn bạn đã chạy file 'open_chrome.bat' trước khi bắt đầu.")
            return

        # Bước 1: Cào danh sách phiếu trên TTS
        state.current_step = "Làm mới & cào danh sách phiếu trên TTS"
        state.log("STEP", "Đang tự động làm mới và quét danh sách phiếu mới nhất trên tab TTS...")
        raw_tickets, tts_tab_handle = get_vnpt_tickets(driver, service_type="data")

        if not raw_tickets:
            state.log("WARN", "Không tìm thấy phiếu nào trên trang TTS hiện tại.")
            return

        total_tickets = len(raw_tickets)
        state.total_scanned += total_tickets
        state.log("SUCCESS", f"Thu được {total_tickets} thuê bao từ TTS. Bắt đầu tra cứu Core...")

        # Đồng bộ danh sách phiếu hiện hữu với thực tế trên web TTS
        scanned_phones = set()
        for t in raw_tickets:
            p = str(t.get("phone", "")).strip()
            if p:
                if not p.startswith("84"):
                    p = "84" + p
                scanned_phones.add(p)
        if scanned_phones:
            sync_active_tickets_state(scanned_phones, source="tts_old", key_type="phone", service_type="data")

        now = datetime.now()
        start_d = (now - timedelta(days=4)).strftime("%d%m%Y")
        end_d = now.strftime("%d%m%Y")
        result_dir = BASE_DIR / "result"
        excel_name = result_dir / f"BaoCao_TienKiem_PAKH_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Chuẩn bị tab BTools
        btools_tab_handle = None
        for handle in driver.window_handles:
            if handle != tts_tab_handle:
                try:
                    driver.switch_to.window(handle)
                    if "10.159.21.241" in driver.current_url.lower():
                        btools_tab_handle = handle
                        break
                except Exception:
                    pass

        if not btools_tab_handle:
            driver.switch_to.new_window('tab')
            btools_tab_handle = driver.current_window_handle

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

        # Tải cấu hình danh sách dịch vụ Mobile Internet hợp lệ
        cfg_p = BASE_DIR / "diagnostic_config.json"
        valid_titles = ["Mobile Internet 2G/3G", "Mobile Internet 4G", "Mobile Internet 5G"]
        if cfg_p.exists():
            try:
                with open(cfg_p, "r", encoding="utf-8") as cf:
                    vt = json.load(cf).get("VALID_TITLES", [])
                    if vt:
                        valid_titles = [v for v in vt if "gói cước mobile internet" not in v.lower()]
            except Exception:
                pass

        excel_summary_list = []

        # Bước 2: Tra cứu BTools + SAPC + CEM cho từng số
        for idx, ticket in enumerate(raw_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng trong khi đang xử lý các thuê bao.")
                break

            phone = ticket["phone"]
            title = str(ticket.get("title", "")).strip()
            content = str(ticket.get("content", "")).strip()

            # 🛡️ BỘ LỌC DỊCH VỤ: Chỉ xử lý Mobile Internet, LOẠI TRỪ 'Gói cước Mobile Internet'
            title_lower = title.lower()
            if "gói cước mobile internet" in title_lower:
                state.log("INFO", f"[{idx}/{total_tickets}] Bỏ qua dịch vụ: '{title}' ({phone})")
                continue

            is_valid = any(vt.lower() in title_lower for vt in valid_titles) or ("mobile internet" in title_lower and "gói cước" not in title_lower)
            if not is_valid:
                state.log("INFO", f"[{idx}/{total_tickets}] Bỏ qua dịch vụ không thuộc Mobile Internet: '{title}' ({phone})")
                continue

            phone_84 = normalize_phone_vn(phone)

            state.current_step = f"Tra cứu thuê bao {idx}/{total_tickets}: {phone_84}"
            state.log("INFO", f"[{idx}/{total_tickets}] Đang tra cứu thuê bao: {phone_84} ({title})")

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
                    "btools_technical_data": clean_data if clean_data else []
                }, jf, ensure_ascii=False, indent=4)

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

            # 🎯 BÓC TÁCH THỜI ĐIỂM SỰ CỐ / TIẾP NHẬN
            incident_time_str = ticket.get("incident_time") or extract_incident_time(content, ticket.get("created_time", ""))
            created_time_str = ticket.get("created_time") or incident_time_str

            # Kịch bản phân tích kỹ thuật (kết hợp BTools + SAPC + CEM + App Usage + Mốc thời gian tiếp nhận)
            status, comment, action_plan, color = analyze_subscriber_status(
                clean_data, title, content, phone_84=phone_84, cem_records=cem_records, app_events=app_events, incident_time_str=incident_time_str
            )
            state.log("INFO", f"   ↳ Nhận định: [{status}]")

            # Thu thập hạ tầng
            rats = list(set(str(r.get("RAT_TYPE_NAME", "")) for r in clean_data if r.get("RAT_TYPE_NAME")))
            rat_types_string = ", ".join(rats) if rats else "Không có dữ liệu"

            # Lọc gói cước
            cfg_p = BASE_DIR / "diagnostic_config.json"
            ex_codes = set()
            if cfg_p.exists():
                with open(cfg_p, "r", encoding="utf-8") as cf:
                    ex_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
            
            real_pkgs = set()
            for r in clean_data:
                sc = str(r.get("SERVICE_ID_CODE", "")).strip()
                sn = str(r.get("SERVICE_NAME", "")).strip()
                if sc.lower() and sc.lower() not in ex_codes:
                    if sn and "gói cước lạ" not in sn.lower() and sn.lower() not in ex_codes:
                        real_pkgs.add(sn)
                    else:
                        real_pkgs.add(sc)
            real_pkgs_str = ", ".join(list(real_pkgs)) if real_pkgs else "Không phát sinh gói TM"

            final_packages_str = get_formatted_sapc_packages(phone_84, fallback_btools=real_pkgs_str)

            excel_summary_list.append({
                "phone": phone_84,
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
                "ai_summary": ai_summary if ai_summary else "null"
            })

        # 💾 LƯU TRỮ VÀO SQLITE DATABASE (TỰ ĐỘNG BẢO TOÀN DỮ LIỆU)
        if excel_summary_list:
            save_tickets_bulk(excel_summary_list)
            state.log("SUCCESS", f"Đã lưu/cập nhật {len(excel_summary_list)} phiếu vào Database SQLite.")

        # Xuất Excel phục vụ lưu trữ file
        driver.switch_to.window(tts_tab_handle)
        saved_excel_file = None
        if excel_summary_list:
            state.current_step = "Xuất báo cáo Excel"
            os.makedirs(result_dir, exist_ok=True)
            saved_excel_file = export_diagnostics_to_excel(excel_summary_list, excel_name, start_d, end_d)
            state.log("SUCCESS", f"Báo cáo Excel đã được lưu: {saved_excel_file}")

            if state.open_excel and os.path.exists(saved_excel_file):
                os.startfile(saved_excel_file)

        # Refresh lại tab TTS về trang sự cố
        driver.switch_to.window(tts_tab_handle)
        driver.get("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new")
        time.sleep(2)

        # Bước 3: Tự động đóng phiếu TTS
        if state.auto_close and saved_excel_file:
            state.current_step = "Tự động đóng phiếu trên TTS"
            state.log("STEP", "Đang tiến hành tự động điền form và đóng phiếu TTS...")
            from update_tts.run import run_update_tts
            success = run_update_tts(
                excel_path=saved_excel_file,
                dry_run=False,
                observe=False
            )
            if success:
                state.log("SUCCESS", "Hoàn tất cập nhật và đóng phiếu TTS trong chu kỳ này!")

        state.total_cycles += 1
        state.last_run_time = datetime.now().strftime("%H:%M:%S")

        # 🧹 Tự động đóng toàn bộ các tab trống rác
        from tab_cleaner import close_blank_tabs
        close_blank_tabs(driver)

    except Exception as e:
        state.log("ERROR", f"Lỗi phát sinh trong chu kỳ: {e}")
    finally:
        state.current_step = "Hoàn tất chu kỳ"




# Alias tương thích
execute_one_cycle = execute_tts_old_data_cycle
