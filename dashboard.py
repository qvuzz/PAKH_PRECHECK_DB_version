# dashboard.py
# Hệ Thống Tiền Kiểm Phản Ánh Khách Hàng (PAKH Precheck) - VNPT
# Web Dashboard Server & Controller

import os
import sys
import json
import time
import socket
import threading
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = Path(__file__).resolve().parent
PORT = 1234
TEMPLATE_PATH = BASE_DIR / "templates" / "dashboard.html"

# Database operations
from db_manager import (
    init_db, 
    get_all_tickets, 
    get_system_counts, 
    delete_all_tickets, 
    get_db_connection, 
    update_ticket_field
)

# Services & Modules
from services.state import state, normalize_phone_vn
from services.tts_old_data import execute_tts_old_data_cycle, execute_one_cycle
from services.tts_old_voice import execute_tts_old_voice_cycle
from services.tts_new_data import execute_tts_new_data_cycle, execute_ttsnew_cycle
from services.tts_new_voice import execute_tts_new_voice_cycle
from services.automation_worker import automation_worker_loop


def load_dashboard_html() -> str:
    """Đọc template HTML từ templates/dashboard.html."""
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Lỗi: Không tìm thấy file templates/dashboard.html</h1>"


# ==============================================================================
# HTTP REQUEST HANDLER & REST API ROUTER
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

        # 1. Trang chủ Dashboard
        if parsed.path == "/" or parsed.path == "/index.html":
            body = load_dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # 2. Logo VNPT
        elif parsed.path in ("/vnpt-logo.svg", "/favicon.ico"):
            logo_path = os.path.join(BASE_DIR, "vnpt-logo.svg")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Not Found")

        # 3. Trạng thái live
        elif parsed.path == "/api/status":
            self._send_json(state.get_snapshot())

        # 4. Danh sách phiếu
        elif parsed.path == "/api/tickets":
            search = qs.get("search", [None])[0]
            status_filter = qs.get("status", [None])[0]
            tab = qs.get("tab", [None])[0]
            source = qs.get("source", ["tts_old"])[0]
            service_type = qs.get("service_type", ["data"])[0]
            if source == "all": source = None
            if service_type == "all": service_type = None

            tickets = get_all_tickets(
                search=search, 
                status_filter=status_filter, 
                tab_filter=tab, 
                source=source, 
                service_type=service_type
            )
            sys_counts = get_system_counts()
            all_raw = get_all_tickets(source=source, service_type=service_type)
            closed_cnt = sum(1 for t in all_raw if t.get("ticket_status") == "Đã đóng")
            active_cnt = len(all_raw) - closed_cnt

            self._send_json({
                "tickets": tickets,
                "total_count": len(all_raw),
                "closed_count": closed_cnt,
                "active_count": active_cnt,
                "system_counts": sys_counts
            })

        # 5. Xuất Excel
        elif parsed.path == "/api/export_excel":
            from report_bot import export_diagnostics_to_excel
            source = qs.get("source", ["tts_old"])[0]
            if source == "all": source = None
            tickets = get_all_tickets(source=source)
            if not tickets:
                self.send_error(400, "Database trống, chưa có phiếu để xuất Excel.")
                return

            out_dir = BASE_DIR / "result"
            os.makedirs(out_dir, exist_ok=True)
            prefix = "BaoCao_TTS_NEW" if source == "tts_new" else "BaoCao_TTS_OLD"
            out_file = out_dir / f"{prefix}_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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

        # 1. Bật tự động
        if parsed.path == "/api/start":
            state.is_running = True
            state.stop_requested = False
            state.status_message = "Đã khởi động tiến trình tự động."
            if "auto_close" in body:
                state.auto_close = bool(body["auto_close"])
                mode_str = "TỰ ĐỘNG ĐÓNG" if state.auto_close else "ĐÓNG THỦ CÔNG"
                state.log("INFO", f"⚙️ Đã chuyển chế độ đóng phiếu sang: [{mode_str}]")
            if "interval_minutes" in body:
                state.interval_minutes = int(body["interval_minutes"])
            self._send_json({"success": True, "auto_close": state.auto_close})

        # 2. Dừng tự động
        elif parsed.path == "/api/stop":
            state.stop_requested = True
            state.is_running = False
            state.log("WARN", "⏹️ DỪNG VÒNG LẶP TỰ ĐỘNG.")
            self._send_json({"success": True})

        # 3. Quét ngay TTS Cũ (Mobile Internet)
        elif parsed.path == "/api/run-now":
            state.trigger_now_requested = True
            state.is_running = True
            state.stop_requested = False
            state.log("INFO", "⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC (TTS CŨ - DATA)!")
            self._send_json({"success": True})

        # 4. Quét TTS Cũ (Thoại / SMS / Gói)
        elif parsed.path == "/api/tts_old/scan_voice":
            if state.is_running:
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_old_voice_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đang tiến hành quét riêng phiếu Thoại / SMS từ TTS Cũ..."})

        # 5. Quét TTS Mới (Mobile Internet)
        elif parsed.path == "/api/ttsnew/run-now":
            if state.is_running:
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_new_data_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đã kích hoạt quét tiền kiểm REST API TTS Mới..."})

        # 6. Quét TTS Mới (Thoại / SMS / Gói)
        elif parsed.path == "/api/ttsnew/scan_voice":
            if state.is_running:
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_new_voice_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đang tiến hành quét phiếu Thoại / SMS từ TTS Mới qua REST API..."})

        # 7. Mở chi tiết phiếu trên TTS Mới (chi-tiet-phieu-pakh)
        elif parsed.path == "/api/ttsnew/open_detail":
            ticket_code = str(body.get("ticket_code") or "").strip()
            phone = str(body.get("phone") or "").strip()
            incident_time = str(body.get("incident_time") or "").strip()

            conn = get_db_connection()
            row = None
            if ticket_code:
                row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id FROM tickets WHERE ticket_code = ?", (ticket_code,)).fetchone()
            if not row and phone:
                row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id FROM tickets WHERE phone = ? AND source = 'tts_new'", (phone,)).fetchone()
            conn.close()

            ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
            flow_id = row["flow_id"] if (row and row["flow_id"]) else None
            code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code

            if not ticket_id and code and "/" in code:
                try:
                    ticket_id = int(code.split("/")[-1])
                except Exception:
                    pass

            if not flow_id:
                try:
                    from ttsnew_api import extract_token_from_browser, fetch_active_tickets
                    tok = extract_token_from_browser()
                    if tok:
                        active_t = fetch_active_tickets(tok, limit=1000)
                        for at in active_t:
                            if at.get("ticketCode") == code or (ticket_id and at.get("ticketId") == ticket_id):
                                flow_id = at.get("id")
                                ticket_id = at.get("ticketId")
                                conn_u = get_db_connection()
                                with conn_u:
                                    conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE ticket_code = ?", (flow_id, ticket_id, code))
                                conn_u.close()
                                break
                except Exception as ex_f:
                    state.log("WARN", f"Không tìm thấy flow_id cho {code}: {ex_f}")

            if not flow_id or not ticket_id:
                self._send_json({"success": False, "message": f"Không tìm thấy mã luồng (flow_id/ticket_id) của phiếu {code or phone}."})
                return

            state.log("STEP", f"🌐 Đang chuyển màn hình tới chi tiết phiếu {code} trên tab TTS Mới...")

            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    context = browser.contexts[0]
                    target_page = None
                    for pg in context.pages:
                        if "tts.vnptnet.vn" in pg.url:
                            target_page = pg
                            break
                    if not target_page:
                        target_page = context.new_page()
                        target_page.goto("https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh")
                        target_page.wait_for_timeout(1000)

                    target_page.bring_to_front()
                    target_page.evaluate(f"""() => {{
                        window.history.pushState({{ ticketFlowId: {flow_id}, ticketId: {ticket_id}, ticketTypeId: 2 }}, '', '/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh');
                        window.location.reload();
                    }}""")
                state.log("SUCCESS", f"✅ Đã mở tab chi tiết phiếu {code} (ID: {ticket_id}) trên TTS Mới!")
                self._send_json({
                    "success": True, 
                    "message": f"Đã mở chi tiết phiếu {code} trên TTS Mới", 
                    "ticket_code": code,
                    "ticket_id": ticket_id,
                    "flow_id": flow_id
                })
            except Exception as ex_open:
                state.log("WARN", f"⚠️ Lỗi mở tab TTS Mới: {ex_open}")
                self._send_json({"success": False, "message": f"Lỗi mở tab TTS Mới: {str(ex_open)}"})

        # 8. Tiền kiểm thủ công 1 thuê bao (SAPC / Cell / HSS)
        elif parsed.path == "/api/tickets/precheck_one":
            phone = body.get("phone")
            incident_time = body.get("incident_time")
            if not phone:
                self.send_error(400, "Missing phone")
                return

            state.log("STEP", f"⚡ Đang thực hiện tiền kiểm tra nhanh cho thuê bao {phone}...")

            try:
                SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
                if SAPCCHECK_DIR not in sys.path:
                    sys.path.insert(0, SAPCCHECK_DIR)
                from sapc_client import SAPCClient
                from msisdn_info import tra_cell_tu_so_dien_thoai
                from converter import convert_sapc_response
                from report_bot import get_formatted_sapc_packages, analyze_subscriber_status
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options

                sapc_client = None
                try:
                    options = Options()
                    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    driver = webdriver.Chrome(options=options)
                    sapc_client = SAPCClient(driver=driver)
                except Exception:
                    try:
                        sapc_client = SAPCClient()
                    except Exception:
                        pass

                # 1. Tra cứu HSS / HLR / Cell / NAM
                info_res = {}
                try:
                    info_res = tra_cell_tu_so_dien_thoai(phone, session=sapc_client.session if sapc_client else None)
                except Exception as ex_cell:
                    state.log("WARN", f"Lỗi tra cứu Cell/HLR cho {phone}: {ex_cell}")

                # 2. Tra cứu SAPC gói cước
                sapc_res = {"msisdn": phone, "packages": []}
                try:
                    if sapc_client:
                        raw_sapc = sapc_client.query(phone)
                        sapc_res = convert_sapc_response(raw_sapc)
                except Exception as ex_sapc:
                    state.log("WARN", f"Lỗi tra cứu gói cước SAPC cho {phone}: {ex_sapc}")

                # 3. Lưu file output/{phone}.json
                out_dir = str(BASE_DIR / "output")
                os.makedirs(out_dir, exist_ok=True)
                with open(os.path.join(out_dir, f"{phone}.json"), "w", encoding="utf-8") as f:
                    json.dump({
                        **sapc_res,
                        "subscriber_info": info_res,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, f, ensure_ascii=False, indent=4)

                formatted_pkg = get_formatted_sapc_packages(phone)
                cell_desc = info_res.get("Cell ID") or info_res.get("ECGI") or "--"
                rat = info_res.get("Radio") or "Sóng di động"

                conn = get_db_connection()
                with conn:
                    cur = conn.execute("SELECT package_title, ticket_content FROM tickets WHERE phone = ?", (phone,))
                    row = cur.fetchone()
                    pkg_title = row[0] if row else "Thoại / SMS"
                    t_content = row[1] if row else ""
                    
                    status_calc, comment_calc, action_calc, _ = analyze_subscriber_status(
                        [], pkg_title, t_content, phone_84=phone, incident_time_str=incident_time
                    )

                    conn.execute("""
                        UPDATE tickets 
                        SET real_packages = ?, 
                            rat_types = ?,
                            cem_data = ?,
                            status = ?,
                            comment = ?,
                            action_plan = ?,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE phone = ?
                    """, (formatted_pkg, rat, f"Cell: {cell_desc}", status_calc, comment_calc, action_calc, phone))
                conn.close()

                state.log("SUCCESS", f"✅ Đã tiền kiểm Core xong cho {phone}: Radio={info_res.get('Radio')}, HSS={info_res.get('HSS Profile')}, IP={info_res.get('IPv4')}, NAM={info_res.get('NAM')}")
                self._send_json({"success": True, "formatted_pkg": formatted_pkg, "info": info_res})
            except Exception as ex_pre:
                state.log("WARN", f"⚠️ Lỗi tiền kiểm tra cho {phone}: {ex_pre}")
                self._send_json({"success": False, "error": str(ex_pre)})

        # 9. Đóng thủ công phiếu TTS Cũ
        elif parsed.path == "/api/tickets/close_one":
            phone = body.get("phone")
            incident_time = body.get("incident_time")
            if not phone:
                self.send_error(400, "Missing phone")
                return

            state.log("STEP", f"Đang thực hiện đóng thủ công phiếu cho SĐT {phone} trên TTS Cũ...")
            from update_tts.run import close_single_ticket_from_db
            success, message = close_single_ticket_from_db(
                phone=phone,
                incident_time=incident_time,
                dry_run=False,
                observe=False
            )
            if success:
                state.log("SUCCESS", f"✅ {message}")
            else:
                state.log("WARN", f"⚠️ {message}")
            self._send_json({"success": success, "message": message})

        # 10. Cập nhật ý kiến phân tích / phương án xử lý
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

        # 11. Xóa toàn bộ dữ liệu database
        elif parsed.path == "/api/tickets/clear":
            source = body.get("source") if body else None
            delete_all_tickets(source=source)
            state.total_scanned = 0
            state.closed_count = 0
            sys_text = "TTS Mới" if source == "tts_new" else ("TTS Cũ" if source == "tts_old" else "toàn bộ")
            state.log("WARN", f"🗑️ Đã xóa sạch dữ liệu phiếu ({sys_text}) trong SQLite Database.")
            self._send_json({"success": True})

        else:
            self.send_error(404, "Not Found")


# ==============================================================================
# QUẢN LÝ CHROME DEBUGGING & TRÌNH DUYỆT
# ==============================================================================
def launch_chrome_debug():
    """Kiểm tra hoặc khởi chạy Google Chrome ở chế độ Debugging (port 9222)."""
    try:
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
    """Mở hoặc kích hoạt URL trong phiên Chrome Debug đang chạy."""
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

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for cp in chrome_paths:
        if os.path.exists(cp):
            subprocess.Popen([cp, "--remote-debugging-port=9222", "--user-data-dir=C:\\ChromeDebugProfile", url])
            return


# ==============================================================================
# KHỞI CHẠY MÁY CHỦ WEB DASHBOARD
# ==============================================================================
def run_dashboard():
    init_db()
    launch_chrome_debug()

    # Khởi chạy luồng lặp tự động nền
    worker_thread = threading.Thread(target=automation_worker_loop, daemon=True)
    worker_thread.start()

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print("================================================================")
    print(f"[PAKH Precheck] Web Dashboard dang chay tai: http://localhost:{PORT}")
    print("================================================================")
    
    open_in_chrome_debug(f"http://localhost:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[PAKH Precheck] Dang tat Dashboard Server...")
        server.server_close()


if __name__ == "__main__":
    run_dashboard()
