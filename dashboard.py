import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Đảm bảo tương thích khi chạy ẩn qua pythonw (sys.stdout/stderr là None)
log_file_path = os.path.join(os.path.dirname(__file__), "dashboard_service.log")
if sys.stdout is None:
    try:
        sys.stdout = open(log_file_path, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w")
elif hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if sys.stderr is None:
    try:
        sys.stderr = open(log_file_path, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w")
elif hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
PORT = 1234

from db_manager import init_db, save_or_update_ticket, save_tickets_bulk, get_all_tickets, update_ticket_field, delete_all_tickets

# ==============================================================================
# QUẢN LÝ TRẠNG THÁI TIẾN TRÌNH VÀ VÒNG LẶP TOÀN CỤC
# ==============================================================================
class AutomationState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.status = "IDLE"  # IDLE, PROCESSING, WAITING, STOPPING
        self.status_message = "Sẵn sàng khởi động"
        self.interval_minutes = 5
        self.auto_close = True
        self.dry_run = False
        self.observe = False
        self.open_excel = False

        # Thống kê
        self.total_cycles = 0
        self.total_scanned = 0
        self.total_closed = 0
        self.last_run_time = None
        self.countdown_seconds = 0
        self.current_step = ""

        # Hàng đợi log
        self.logs = []
        self.max_logs = 300

        # Sự kiện ngắt chờ
        self.stop_requested = False
        self.trigger_now_requested = False

    def log(self, level, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": timestamp,
            "level": level.upper(),  # INFO, SUCCESS, WARN, ERROR, STEP
            "message": str(message)
        }
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
        # In ra terminal an toàn trên mọi hệ điều hành
        prefix = f"[{timestamp}] [{level.upper()}]"
        try:
            print(f"{prefix} {message}")
        except Exception:
            try:
                print(f"{prefix} {str(message).encode('ascii', errors='replace').decode('ascii')}")
            except Exception:
                pass

    def get_snapshot(self):
        with self.lock:
            return {
                "is_running": self.is_running,
                "status": self.status,
                "status_message": self.status_message,
                "interval_minutes": self.interval_minutes,
                "auto_close": self.auto_close,
                "dry_run": self.dry_run,
                "observe": self.observe,
                "open_excel": self.open_excel,
                "total_cycles": self.total_cycles,
                "total_scanned": self.total_scanned,
                "total_closed": self.total_closed,
                "last_run_time": self.last_run_time,
                "countdown_seconds": self.countdown_seconds,
                "current_step": self.current_step,
                "logs": list(self.logs)
            }

state = AutomationState()


# ==============================================================================
# HÀM THỰC THI 1 CHU KỲ KIỂM TRA TOÀN DIỆN
# ==============================================================================
def execute_one_cycle():
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
        state.current_step = "Cào danh sách phiếu trên TTS"
        state.log("STEP", "Đang quét danh sách phiếu trên tab TTS...")
        raw_tickets, tts_tab_handle = get_vnpt_tickets(driver)

        if not raw_tickets:
            state.log("WARN", "Không tìm thấy phiếu nào trên trang TTS hiện tại.")
            return

        total_tickets = len(raw_tickets)
        state.total_scanned += total_tickets
        state.log("SUCCESS", f"Thu được {total_tickets} thuê bao từ TTS. Bắt đầu tra cứu Core...")

        now = datetime.now()
        start_d = (now - timedelta(days=4)).strftime("%Y-%m-%d")
        end_d = now.strftime("%Y-%m-%d")
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

            phone_84 = "84" + phone[1:] if phone.startswith("0") else (phone if phone.startswith("84") else "84" + phone)

            state.current_step = f"Tra cứu thuê bao {idx}/{total_tickets}: {phone_84}"
            state.log("INFO", f"[{idx}/{total_tickets}] Đang tra cứu thuê bao: {phone_84} ({title})")

            # Tra cứu BTools
            driver.switch_to.window(btools_tab_handle)
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
            incident_time_str = extract_incident_time(content, ticket.get("created_time", ""))

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
                "created_time": ticket.get("created_time", ""),
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
        if (state.auto_close or state.dry_run) and saved_excel_file:
            state.current_step = "Tự động đóng phiếu trên TTS"
            state.log("STEP", "Đang tiến hành tự động điền form và đóng phiếu TTS...")
            from update_tts.run import run_update_tts
            success = run_update_tts(
                excel_path=saved_excel_file,
                dry_run=state.dry_run,
                observe=state.observe
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


# ==============================================================================
# LUỒNG LẶP NỀN (BACKGROUND WORKER THREAD)
# ==============================================================================
def automation_worker_loop():
    while True:
        if not state.is_running and not state.trigger_now_requested:
            state.status = "IDLE"
            state.status_message = "Đã dừng. Sẵn sàng nhận lệnh START."
            time.sleep(0.5)
            continue

        state.is_running = True
        state.trigger_now_requested = False

        # Thực thi chu kỳ
        execute_one_cycle()

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


worker_thread = threading.Thread(target=automation_worker_loop, daemon=True)
worker_thread.start()


# ==============================================================================
# GIAO DIỆN WEB DASHBOARD + INTERACTIVE GRID + INLINE EDIT
# ==============================================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PAKH Precheck — Hệ Thống Tiền Kiểm VNPT</title>
    <style>
        :root {
            --bg-page: #f8fafc;
            --bg-surface: #ffffff;
            --border-color: #e2e8f0;
            --border-focus: #005baa;
            --text-heading: #0f172a;
            --text-body: #334155;
            --text-muted: #64748b;
            --primary: #005baa;
            --primary-hover: #004684;
            --success: #16a34a;
            --warning: #d97706;
            --danger: #dc2626;
            --radius-sm: 4px;
            --radius-md: 6px;
            --radius-lg: 8px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-page);
            color: var(--text-body);
            min-height: 100vh;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            -webkit-font-smoothing: antialiased;
        }

        /* HEADER */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 18px;
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        }

        .logo-area { display: flex; align-items: center; gap: 12px; }
        .logo-tag {
            background: var(--primary);
            color: #ffffff;
            font-size: 11px;
            font-weight: 800;
            padding: 4px 7px;
            border-radius: var(--radius-sm);
            letter-spacing: 0.05em;
        }
        .logo-title { font-size: 15px; font-weight: 700; color: var(--text-heading); }
        .logo-divider { color: #cbd5e1; font-weight: 300; }
        .logo-subtitle { font-size: 13px; color: var(--text-muted); font-weight: 500; }

        .system-pill {
            display: flex; align-items: center; gap: 8px;
            padding: 5px 12px; border-radius: 20px;
            background: #f1f5f9; border: 1px solid var(--border-color);
            font-size: 12.5px; font-weight: 500; color: var(--text-heading);
        }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--text-muted);
        }
        .status-dot.active { background: var(--success); }
        .status-dot.waiting { background: var(--warning); animation: pulse 1.5s infinite; }
        .status-dot.processing { background: var(--primary); animation: pulse 0.8s infinite; }

        @keyframes pulse { 0% { opacity: 0.3; } 50% { opacity: 1; } 100% { opacity: 0.3; } }

        /* STATS GRID */
        .grid-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
        }
        .card-stat {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 12px 16px;
            display: flex; flex-direction: column; gap: 4px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }
        .stat-label { 
            font-size: 11px; color: var(--text-muted); font-weight: 600; 
            text-transform: uppercase; letter-spacing: 0.04em; 
        }
        .stat-val { 
            font-size: 20px; font-weight: 700; color: var(--text-heading); 
            font-feature-settings: "tnum"; font-variant-numeric: tabular-nums;
        }
        .stat-val.primary { color: var(--primary); }
        .stat-val.success { color: var(--success); }

        /* MAIN LAYOUT */
        .main-layout {
            display: grid;
            grid-template-columns: 310px 1fr;
            gap: 16px;
        }

        /* CONTROL PANEL */
        .panel-control {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 16px;
            display: flex; flex-direction: column; gap: 14px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }
        .panel-title { 
            font-size: 13.5px; font-weight: 700; color: var(--text-heading); 
            border-bottom: 1px solid var(--border-color); padding-bottom: 10px; 
            display: flex; justify-content: space-between; align-items: center;
        }

        .control-group { display: flex; flex-direction: column; gap: 5px; }
        .control-label { font-size: 12.5px; font-weight: 600; color: var(--text-heading); }
        .control-input {
            width: 100%; padding: 7px 10px;
            background: #ffffff; border: 1px solid #cbd5e1;
            border-radius: var(--radius-sm); color: var(--text-heading); font-size: 13px;
            font-family: inherit; outline: none; transition: border-color 0.15s;
        }
        .control-input:focus { border-color: var(--border-focus); box-shadow: 0 0 0 2px rgba(0, 91, 170, 0.12); }

        .toggle-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 10px; background: #f8fafc;
            border-radius: var(--radius-sm); border: 1px solid var(--border-color);
            font-size: 12.5px; font-weight: 500; color: var(--text-heading);
        }
        .switch { position: relative; display: inline-block; width: 36px; height: 20px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background-color: #cbd5e1; transition: .2s; border-radius: 20px;
        }
        .slider:before {
            position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px;
            background-color: white; transition: .2s; border-radius: 50%;
        }
        input:checked + .slider { background-color: var(--primary); }
        input:checked + .slider:before { transform: translateX(16px); }

        /* BUTTONS */
        .btn {
            padding: 8px 14px; border-radius: var(--radius-sm);
            font-size: 13px; font-weight: 600; cursor: pointer;
            display: inline-flex; align-items: center; justify-content: center; gap: 7px;
            transition: all 0.15s ease; border: 1px solid transparent;
            font-family: inherit; text-decoration: none;
        }
        .btn svg { width: 15px; height: 15px; flex-shrink: 0; fill: currentColor; }

        .btn-primary { 
            background: var(--primary); color: #ffffff; 
            border-color: var(--primary); 
        }
        .btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); }

        .btn-secondary { 
            background: #ffffff; color: var(--text-heading); 
            border-color: #cbd5e1; 
        }
        .btn-secondary:hover { background: #f8fafc; border-color: #94a3b8; }

        .btn-outline-primary { 
            background: #ffffff; color: var(--primary); 
            border-color: var(--primary); font-weight: 600; 
        }
        .btn-outline-primary:hover { background: var(--primary); color: #ffffff; }

        .btn-ghost-danger { 
            background: #ffffff; color: var(--text-muted); 
            border-color: var(--border-color); font-weight: 500; 
        }
        .btn-ghost-danger:hover { 
            background: #fef2f2; color: var(--danger); border-color: #fca5a5; 
        }

        .btn-icon {
            padding: 6px; width: 32px; height: 32px;
            background: #ffffff; border: 1px solid #cbd5e1;
            color: var(--text-muted); border-radius: var(--radius-sm);
        }
        .btn-icon:hover { background: #f8fafc; border-color: var(--primary); color: var(--primary); }

        .btn-danger { 
            background: var(--danger); color: #fff; border-color: var(--danger); 
        }
        .btn-danger:hover { background: #b91c1c; }

        /* DATA TABLE PANEL */
        .panel-table {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 16px;
            display: flex; flex-direction: column; gap: 12px;
            overflow: hidden;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }

        .table-toolbar {
            display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .search-box {
            flex: 1; min-width: 180px; max-width: 280px;
            position: relative;
        }
        .search-box input {
            width: 100%; padding: 6px 10px 6px 30px;
            background: #ffffff; border: 1px solid #cbd5e1;
            border-radius: var(--radius-sm); color: var(--text-heading); font-size: 12.5px; outline: none;
        }
        .search-box input:focus { border-color: var(--border-focus); }
        .search-box::before {
            content: "🔍"; position: absolute; left: 8px; top: 6px; font-size: 11px; opacity: 0.5;
        }

        .table-container {
            width: 100%; max-height: 540px; overflow: auto;
            border-radius: var(--radius-sm); border: 1px solid var(--border-color);
        }
        table {
            width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;
        }
        thead {
            position: sticky; top: 0; background: #f8fafc; z-index: 10;
        }
        th {
            padding: 9px 12px; font-weight: 600; color: #475569;
            border-bottom: 1px solid var(--border-color); white-space: nowrap;
            text-transform: uppercase; font-size: 11px; letter-spacing: 0.03em;
        }
        td {
            padding: 8px 12px; border-bottom: 1px solid #f1f5f9;
            vertical-align: top; background: #ffffff; color: var(--text-body);
        }
        tr:nth-child(even) td { background: #fafbfc; }
        tr:hover td { background: #f1f5f9 !important; }

        /* BADGES */
        .badge-status {
            display: inline-block; padding: 2px 6px; border-radius: 4px;
            font-size: 10.5px; font-weight: 600; white-space: nowrap;
        }
        .badge-green { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
        .badge-yellow { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
        .badge-gray { background: #f8fafc; color: #475569; border: 1px solid #e2e8f0; }
        .badge-cyan { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }

        .editable-cell {
            width: 100%; min-height: 48px; background: #ffffff;
            border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 8px;
            color: var(--text-heading); font-family: inherit; font-size: 11.5px; resize: vertical;
            transition: border-color 0.15s; line-height: 1.4;
        }
        .editable-cell:focus {
            border-color: var(--border-focus); outline: none;
            box-shadow: 0 0 0 2px rgba(0, 91, 170, 0.12);
        }

        .save-indicator {
            font-size: 10.5px; color: var(--success); font-weight: 600; display: none; margin-top: 2px;
        }

        /* LOG PANEL */
        .panel-logs {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 14px 16px;
            display: flex; flex-direction: column; gap: 8px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }
        .log-terminal {
            height: 160px; overflow-y: auto;
            background: #ffffff; border-radius: var(--radius-sm);
            padding: 10px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11.5px;
            display: flex; flex-direction: column; gap: 4px; border: 1px solid var(--border-color);
        }
        .log-line { display: flex; gap: 8px; align-items: baseline; }
        .log-time { color: #94a3b8; font-size: 11px; white-space: nowrap; }
        .log-level { font-size: 10px; font-weight: 700; padding: 1px 4px; border-radius: 3px; white-space: nowrap; }
        .log-level.INFO { color: #0369a1; background: #f0f9ff; }
        .log-level.SUCCESS { color: #15803d; background: #f0fdf4; }
        .log-level.WARN { color: #b45309; background: #fffbeb; }
        .log-level.ERROR { color: #b91c1c; background: #fef2f2; }
        .log-level.STEP { color: #6d28d9; background: #faf5ff; }
        .log-msg { color: #1e293b; font-weight: 500; }
    </style>
</head>
<body>

    <header>
        <div class="logo-area">
            <span class="logo-tag">VNPT</span>
            <span class="logo-title">PAKH Precheck Engine</span>
            <span class="logo-divider">/</span>
            <span class="logo-subtitle">Tiền kiểm tra sự cố mạng VinaPhone</span>
        </div>
        <div class="system-pill">
            <div id="statusDot" class="status-dot"></div>
            <span id="statusText">Sẵn sàng</span>
        </div>
    </header>

    <div class="grid-stats">
        <div class="card-stat">
            <span class="stat-label">Trạng Thái</span>
            <span id="statStatus" class="stat-val primary">IDLE</span>
        </div>
        <div class="card-stat">
            <span class="stat-label">Phiếu Trong DB</span>
            <span id="statTotalTickets" class="stat-val">0</span>
        </div>
        <div class="card-stat">
            <span class="stat-label">Đã Đóng Thành Công</span>
            <span id="statClosedTickets" class="stat-val success">0</span>
        </div>
        <div class="card-stat">
            <span class="stat-label">Chu Kỳ Đã Chạy</span>
            <span id="statCycles" class="stat-val">0</span>
        </div>
    </div>

    <div class="main-layout">
        <!-- BẢNG ĐIỀU KHIỂN NÚT BẤM -->
        <div class="panel-control">
            <div class="panel-title">
                <span style="display:flex; align-items:center; gap:8px;">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                    Cấu Hình Tự Động
                </span>
                <span id="countdownBadge" style="color:var(--primary); font-family:'JetBrains Mono'; font-weight:700;">--:--</span>
            </div>

            <div class="control-group">
                <label class="control-label">Khoảng cách lặp (Phút)</label>
                <input type="number" id="inpInterval" class="control-input" value="5" min="1" max="60">
            </div>

            <div class="toggle-item">
                <span>Tự động đóng phiếu TTS</span>
                <label class="switch">
                    <input type="checkbox" id="chkAutoClose" checked>
                    <span class="slider"></span>
                </label>
            </div>

            <div class="toggle-item">
                <span>Chế độ chạy thử (Dry-run)</span>
                <label class="switch">
                    <input type="checkbox" id="chkDryRun">
                    <span class="slider"></span>
                </label>
            </div>

            <div class="toggle-item">
                <span>Theo dõi thao tác trên tab (Observe)</span>
                <label class="switch">
                    <input type="checkbox" id="chkObserve">
                    <span class="slider"></span>
                </label>
            </div>

            <div style="display:flex; flex-direction:column; gap:10px; margin-top:6px;">
                <button id="btnStart" class="btn btn-primary" onclick="startAutomation()">
                    <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    Bắt đầu tự động
                </button>
                <button id="btnStop" class="btn btn-danger" onclick="stopAutomation()" style="display:none;">
                    <svg viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
                    Dừng tự động
                </button>
                <button id="btnRunNow" class="btn btn-secondary" onclick="runNow()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                    Quét & Phân tích ngay
                </button>
            </div>
        </div>

        <!-- BẢNG TƯƠNG TÁC DỮ LIỆU THỰC TẾ (INTERACTIVE DATA GRID) -->
        <div class="panel-table">
            <div class="table-toolbar">
                <div style="font-size:15px; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:8px;">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#005baa" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    Danh Sách Phiếu Phản Ánh
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <div class="search-box">
                        <input type="text" id="searchInput" placeholder="Tìm số thuê bao, nội dung..." oninput="loadTickets()">
                    </div>
                    <select id="filterStatus" class="control-input" style="width:140px; padding:7px 10px; font-size:13px;" onchange="loadTickets()">
                        <option value="all">Tất cả phiếu</option>
                        <option value="chua_dong">Chưa đóng</option>
                        <option value="da_dong">Đã đóng</option>
                        <option value="HOẠT ĐỘNG BÌNH THƯỜNG">Bình thường</option>
                        <option value="LƯU LƯỢNG YẾU">Lưu lượng yếu</option>
                    </select>
                    <button class="btn btn-outline-primary" onclick="exportExcel()" title="Tải file Excel báo cáo phân tích 12 cột chuẩn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Xuất Báo Cáo Excel
                    </button>
                    <button class="btn btn-ghost-danger" onclick="clearDatabase()" title="Xóa toàn bộ dữ liệu phiếu trong cơ sở dữ liệu">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                        Xóa Dữ Liệu
                    </button>
                    <button class="btn btn-icon" onclick="loadTickets()" title="Làm mới danh sách">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    </button>
                </div>
            </div>

            <div class="table-container">
                <table id="ticketsTable">
                    <thead>
                        <tr>
                            <th style="width:40px;">STT</th>
                            <th>Nhận Định</th>
                            <th>Số Điện Thoại</th>
                            <th>Ngày Tiếp Nhận</th>
                            <th>Gói Cước SAPC</th>
                            <th>Hạ Tầng</th>
                            <th>Dữ Liệu CEM</th>
                            <th>Nội Dung Phản Ánh</th>
                            <th style="width:260px;">Ý Kiến Phân Tích (Cột 10)</th>
                            <th style="width:260px;">Nội Dung Phản Hồi (Cột 11)</th>
                            <th>Trạng Thái</th>
                        </tr>
                    </thead>
                    <tbody id="ticketsBody">
                        <tr><td colspan="11" style="text-align:center; padding:30px; color:var(--text-muted);">Đang tải dữ liệu phiếu...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- LOG TERMINAL -->
    <div class="panel-logs">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:14px; font-weight:700;">📡 Nhật Ký Xử Lý Hệ Thống (Live Log)</span>
            <span id="currentStepText" style="font-size:12px; color:var(--cyan); font-weight:600;">--</span>
        </div>
        <div id="logTerminal" class="log-terminal"></div>
    </div>

    <script>
        let isRunning = false;

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                isRunning = data.is_running;
                document.getElementById('btnStart').style.display = isRunning ? 'none' : 'flex';
                document.getElementById('btnStop').style.display = isRunning ? 'flex' : 'none';

                const dot = document.getElementById('statusDot');
                dot.className = 'status-dot';
                if (data.status === 'PROCESSING') dot.classList.add('processing');
                else if (data.status === 'WAITING') dot.classList.add('waiting');
                else if (isRunning) dot.classList.add('active');

                document.getElementById('statusText').innerText = data.status_message;
                document.getElementById('statStatus').innerText = data.status;
                document.getElementById('statCycles').innerText = data.total_cycles;
                document.getElementById('currentStepText').innerText = data.current_step || '--';

                if (data.countdown_seconds > 0) {
                    const m = Math.floor(data.countdown_seconds / 60);
                    const s = data.countdown_seconds % 60;
                    document.getElementById('countdownBadge').innerText = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
                } else {
                    document.getElementById('countdownBadge').innerText = '--:--';
                }

                // Render Logs
                const term = document.getElementById('logTerminal');
                const atBottom = term.scrollHeight - term.clientHeight <= term.scrollTop + 40;
                term.innerHTML = data.logs.map(l => `
                    <div class="log-line">
                        <span class="log-time">[${l.time}]</span>
                        <span class="log-level ${l.level}">[${l.level}]</span>
                        <span class="log-msg">${l.message}</span>
                    </div>
                `).join('');
                if (atBottom) term.scrollTop = term.scrollHeight;

            } catch (e) {
                console.error("Lỗi fetch status:", e);
            }
        }

        async function loadTickets() {
            try {
                const search = document.getElementById('searchInput').value;
                const statusFilter = document.getElementById('filterStatus').value;
                const res = await fetch(`/api/tickets?search=${encodeURIComponent(search)}&status=${encodeURIComponent(statusFilter)}`);
                const data = await res.json();
                const tickets = data.tickets || [];

                document.getElementById('statTotalTickets').innerText = data.total_count || tickets.length;
                document.getElementById('statClosedTickets').innerText = data.closed_count || 0;

                const tbody = document.getElementById('ticketsBody');
                if (tickets.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">Chưa có dữ liệu phiếu phản ánh. Hãy nhấn "Quét & Phân tích ngay" để bắt đầu nạp dữ liệu.</td></tr>`;
                    return;
                }

                tbody.innerHTML = tickets.map((t, idx) => {
                    let badgeClass = 'badge-gray';
                    if (t.status.includes('BÌNH THƯỜNG') || t.status.includes('VPN')) badgeClass = 'badge-green';
                    else if (t.status.includes('YẾU') || t.status.includes('GÓI')) badgeClass = 'badge-yellow';

                    const now = new Date();
                    const endD = now.toISOString().slice(0, 10);
                    const startD = new Date(now.getTime() - 4*24*60*60*1000).toISOString().slice(0, 10);
                    const btoolsUrl = `http://10.159.21.241:9267/B_tools_v2/data_view.jsp?name=${t.phone}&start_d=${startD}&end_d=${endD}&submit=T%C3%ACm+Ki%E1%BA%BFm`;

                    return `
                        <tr>
                            <td>${idx + 1}</td>
                            <td><span class="badge-status ${badgeClass}">${t.status}</span></td>
                            <td>
                                <a href="${btoolsUrl}" target="_blank" style="color:var(--cyan); font-weight:700; text-decoration:none;">
                                    ${t.phone} ↗
                                </a>
                                <div style="font-size:11px; color:var(--text-muted);">${t.package_title || ''}</div>
                            </td>
                            <td><span style="color:#ffab00; font-weight:600;">${t.incident_time || '--'}</span></td>
                            <td style="max-width:140px; font-size:11.5px;">${t.real_packages || '--'}</td>
                            <td><span class="badge-status badge-cyan">${t.rat_types || '--'}</span></td>
                            <td style="max-width:120px; font-size:11px;">${t.cem_data || '--'}</td>
                            <td style="max-width:180px; font-size:11.5px;">${t.ticket_content || '--'}</td>
                            <td>
                                <textarea class="editable-cell" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'comment', this.value)">${t.comment || ''}</textarea>
                                <div id="save-comment-${t.phone}-${(t.incident_time||'').replace(/[^a-zA-Z0-9]/g, '_')}" class="save-indicator">✓ Đã lưu tự động</div>
                            </td>
                            <td>
                                <textarea class="editable-cell" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'action_plan', this.value)">${t.action_plan || ''}</textarea>
                                <div id="save-plan-${t.phone}-${(t.incident_time||'').replace(/[^a-zA-Z0-9]/g, '_')}" class="save-indicator">✓ Đã lưu tự động</div>
                            </td>
                            <td>
                                <select class="control-input" style="padding:4px 6px; font-size:11px; width:95px;" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'ticket_status', this.value)">
                                    <option value="Chưa đóng" ${t.ticket_status === 'Chưa đóng' ? 'selected' : ''}>Chưa đóng</option>
                                    <option value="Đã đóng" ${t.ticket_status === 'Đã đóng' ? 'selected' : ''}>Đã đóng</option>
                                </select>
                            </td>
                        </tr>
                    `;
                }).join('');

            } catch (e) {
                console.error("Lỗi load tickets:", e);
            }
        }

        async function updateTicket(phone, incidentTime, field, value) {
            try {
                const res = await fetch('/api/tickets/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone, incident_time: incidentTime, field, value})
                });
                if (res.ok) {
                    const cleanInc = (incidentTime || '').replace(/[^a-zA-Z0-9]/g, '_');
                    const ind = document.getElementById(`save-${field === 'comment' ? 'comment' : 'plan'}-${phone}-${cleanInc}`);
                    if (ind) {
                        ind.style.display = 'block';
                        setTimeout(() => ind.style.display = 'none', 2000);
                    }
                }
            } catch (e) {
                alert("Lỗi khi lưu dữ liệu: " + e);
            }
        }

        async function startAutomation() {
            const interval = parseInt(document.getElementById('inpInterval').value) || 5;
            const autoClose = document.getElementById('chkAutoClose').checked;
            const dryRun = document.getElementById('chkDryRun').checked;
            const observe = document.getElementById('chkObserve').checked;

            await fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({interval_minutes: interval, auto_close: autoClose, dry_run: dryRun, observe})
            });
            fetchStatus();
        }

        async function stopAutomation() {
            await fetch('/api/stop', {method: 'POST'});
            fetchStatus();
        }

        async function runNow() {
            await fetch('/api/run-now', {method: 'POST'});
            fetchStatus();
            setTimeout(loadTickets, 3000);
        }

        function exportExcel() {
            window.location.href = '/api/export_excel';
        }

        async function clearDatabase() {
            if (confirm("⚠️ Bạn có chắc chắn muốn xóa toàn bộ dữ liệu phiếu trong Database không?\\n(Dữ liệu sau khi xóa sẽ không thể phục hồi)")) {
                try {
                    const res = await fetch('/api/tickets/clear', {method: 'POST'});
                    if (res.ok) {
                        loadTickets();
                    }
                } catch (e) {
                    alert("Lỗi khi xóa dữ liệu: " + e);
                }
            }
        }

        setInterval(fetchStatus, 1500);
        setInterval(loadTickets, 10000);
        fetchStatus();
        loadTickets();
    </script>
</body>
</html>
"""

# ==============================================================================
# HTTP REQUEST HANDLER API & WEB SERVER
# ==============================================================================
class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/" or parsed.path == "/index.html":
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/status":
            self._send_json(state.get_snapshot())

        elif parsed.path == "/api/tickets":
            search = qs.get("search", [None])[0]
            status_filter = qs.get("status", [None])[0]
            tickets = get_all_tickets(search=search, status_filter=status_filter)
            
            all_raw = get_all_tickets()
            closed_cnt = sum(1 for t in all_raw if t.get("ticket_status") == "Đã đóng")
            
            self._send_json({
                "tickets": tickets,
                "total_count": len(all_raw),
                "closed_count": closed_cnt
            })

        elif parsed.path == "/api/export_excel":
            from report_bot import export_diagnostics_to_excel
            tickets = get_all_tickets()
            if not tickets:
                self.send_error(400, "Database trống, chưa có phiếu để xuất Excel.")
                return

            out_dir = BASE_DIR / "result"
            os.makedirs(out_dir, exist_ok=True)
            out_file = out_dir / f"BaoCao_PAKH_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            saved_path = export_diagnostics_to_excel(tickets, out_file)

            if os.path.exists(saved_path):
                with open(saved_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f"attachment; filename={os.path.basename(saved_path)}")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(500, "Lỗi tạo file Excel")

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            body = json.loads(post_data)
        except Exception:
            body = {}

        if parsed.path == "/api/start":
            state.interval_minutes = body.get("interval_minutes", state.interval_minutes)
            state.auto_close = body.get("auto_close", state.auto_close)
            state.dry_run = body.get("dry_run", state.dry_run)
            state.observe = body.get("observe", state.observe)
            state.is_running = True
            state.stop_requested = False
            state.log("INFO", f"▶️ BẮT ĐẦU VÒNG LẶP (Interval: {state.interval_minutes} phút, Auto-Close: {state.auto_close})")
            self._send_json({"success": True})

        elif parsed.path == "/api/stop":
            state.stop_requested = True
            state.is_running = False
            state.log("WARN", "⏹️ DỪNG VÒNG LẶP TỰ ĐỘNG.")
            self._send_json({"success": True})

        elif parsed.path == "/api/run-now":
            state.trigger_now_requested = True
            state.is_running = True
            state.stop_requested = False
            state.log("INFO", "⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC!")
            self._send_json({"success": True})

        elif parsed.path == "/api/tickets/update":
            phone = body.get("phone")
            incident_time = body.get("incident_time")
            field = body.get("field")
            value = body.get("value")
            if phone and field:
                ok = update_ticket_field(phone, field, value, incident_time=incident_time)
                self._send_json({"success": ok})
            else:
                self.send_error(400, "Missing phone or field")

        elif parsed.path == "/api/tickets/clear":
            delete_all_tickets()
            state.log("WARN", "🗑️ Đã xóa toàn bộ dữ liệu phiếu trong database theo yêu cầu.")
            self._send_json({"success": True})

        else:
            self.send_error(404, "Not Found")


def launch_chrome_debug():
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        res = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        if res == 0:
            print("✅ Chrome Debugging (Port 9222) đã chạy sẵn.")
            return
    except Exception:
        pass

    bat_file = BASE_DIR / "open_chrome.bat"
    if bat_file.exists():
        subprocess.Popen(["cmd.exe", "/c", "start", "", str(bat_file)], shell=False)


def open_in_chrome_debug(url):
    try:
        import requests
        tabs_res = requests.get("http://127.0.0.1:9222/json/list", timeout=1)
        if tabs_res.status_code == 200:
            tabs = tabs_res.json()
            for t in tabs:
                if f":{PORT}" in t.get("url", ""):
                    requests.get(f"http://127.0.0.1:9222/json/activate/{t.get('id')}", timeout=1)
                    return
        res = requests.get(f"http://127.0.0.1:9222/json/new?{url}", timeout=1)
        if res.status_code == 200:
            return
    except Exception:
        pass

    # Mở thẳng Google Chrome Debug nếu chưa kết nối được
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for cp in chrome_paths:
        if os.path.exists(cp):
            subprocess.Popen([cp, "--remote-debugging-port=9222", "--user-data-dir=C:\\ChromeDebugProfile", url])
            return


def run_dashboard():
    init_db()
    launch_chrome_debug()

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print("================================================================")
    print(f"🎛️  PAKH PRECHECK WEB DASHBOARD ĐANG CHẠY TẠI: http://localhost:{PORT}")
    print("================================================================")
    
    open_in_chrome_debug(f"http://localhost:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Đang tắt Dashboard Server...")
        server.server_close()


if __name__ == "__main__":
    run_dashboard()
