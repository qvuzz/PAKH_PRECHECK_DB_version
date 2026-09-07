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

# Bảo vệ khi chạy ngầm bằng pythonw (tránh NoneType write error)
if sys.stdout is None:
    try:
        sys.stdout = open(BASE_DIR / "dashboard_service.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    try:
        sys.stderr = open(BASE_DIR / "dashboard_service.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w")

# Database operations
from db_manager import (
    init_db, 
    get_all_tickets, 
    get_system_counts, 
    delete_all_tickets, 
    get_db_connection, 
    update_ticket_field,
    get_closed_tickets_analytics
)

# Services & Modules
from services.state import state, normalize_phone_vn
from services.tts_old_api_data import execute_tts_old_api_data_cycle
from services.tts_old_api_voice import execute_tts_old_api_voice_cycle

from services.tts_new_data import execute_tts_new_data_cycle, execute_ttsnew_cycle
from services.tts_new_voice import execute_tts_new_voice_cycle
from tts_old_api import close_tts_old_ticket_api, fetch_nguyen_nhan_list_api, extract_token_from_browser, save_cached_auth
from services.automation_worker import automation_worker_loop

execute_tts_old_data_cycle = execute_tts_old_api_data_cycle
execute_one_cycle = execute_tts_old_api_data_cycle
execute_tts_old_voice_cycle = execute_tts_old_api_voice_cycle


def load_dashboard_html() -> str:
    """Đọc template HTML từ templates/dashboard.html."""
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Lỗi: Không tìm thấy file templates/dashboard.html</h1>"


ACTIVE_LAN_SESSIONS = {}

# ==============================================================================
# HTTP REQUEST HANDLER & ROUTER
# ==============================================================================
class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Trang chủ Dashboard
        if parsed.path == "/" or parsed.path == "/index.html":
            body = load_dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        # 1.1 Tệp tĩnh Static (CSS, JS, Fonts, Ảnh)
        elif parsed.path.startswith("/static/"):
            rel_path = parsed.path.lstrip("/").replace("/", os.sep)
            static_file = BASE_DIR / rel_path
            if static_file.exists() and static_file.is_file():
                content_type = "application/octet-stream"
                if parsed.path.endswith(".css"):
                    content_type = "text/css; charset=utf-8"
                elif parsed.path.endswith(".js"):
                    content_type = "application/javascript; charset=utf-8"
                elif parsed.path.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif parsed.path.endswith(".png"):
                    content_type = "image/png"
                elif parsed.path.endswith(".json"):
                    content_type = "application/json; charset=utf-8"
                
                with open(static_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Static File Not Found")

        # 2. Logo VNPT
        elif parsed.path in ("/vnpt-logo.svg", "/vnpt-logo-horizontal.svg", "/favicon.ico"):
            file_name = "vnpt-logo-horizontal.svg" if "horizontal" in parsed.path else "vnpt-logo.svg"
            logo_path = os.path.join(BASE_DIR, file_name)
            if not os.path.exists(logo_path):
                logo_path = os.path.join(BASE_DIR, "vnpt-logo.svg")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Not Found")

        # 3. Trạng thái live
        elif parsed.path == "/api/status":
            snap = state.get_snapshot()
            snap["system_counts"] = get_system_counts()
            self._send_json(snap)

        # 3.1 Thông tin xác thực tài khoản & phân quyền (Local & LAN)
        elif parsed.path == "/api/current_user":
            client_ip = self.client_address[0]
            is_local = client_ip in ("127.0.0.1", "localhost", "::1")
            
            token = ""
            user_info = {}
            if client_ip in ACTIVE_LAN_SESSIONS and (time.time() - ACTIVE_LAN_SESSIONS[client_ip].get("timestamp", 0) < 86400):
                token = ACTIVE_LAN_SESSIONS[client_ip].get("token", "")
                user_info = ACTIVE_LAN_SESSIONS[client_ip].get("user", {})
            elif is_local:
                # CHỈ lấy từ Chrome Debug trên máy chủ NẾU request xuất phát từ chính máy chủ (Localhost)
                token, user_info = extract_token_from_browser()

            self._send_json({
                "is_local": is_local,
                "client_ip": client_ip,
                "has_server_token": bool(token),
                "server_user": user_info,
                "server_token": token
            })

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

        # 4.1. Thống kê phân tích chuyên sâu các phiếu đã đóng
        elif parsed.path == "/api/tickets/closed_stats":
            period = qs.get("period", ["all"])[0]
            source = qs.get("source", ["all"])[0]
            service_type = qs.get("service_type", ["all"])[0]
            if source == "all": source = None
            if service_type == "all": service_type = None
            stats = get_closed_tickets_analytics(time_filter=period, source_filter=source, service_filter=service_type)
            self._send_json(stats)

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
        elif parsed.path == "/api/logs/clear":
            state.clear_logs()
            self._send_json({"success": True, "message": "Đã xóa toàn bộ nhật ký"})

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        try:
            self._handle_post()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"success": False, "message": f"Lỗi máy chủ: {str(e)}"}, status=500)

    def _handle_post(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            body = json.loads(post_data)
        except Exception:
            body = {}

        # Xóa hàng đợi log
        if parsed.path == "/api/logs/clear":
            state.clear_logs()
            self._send_json({"success": True, "message": "Đã xóa toàn bộ nhật ký"})
            return

        # 0. Đăng ký phiên KTV từ extension hoặc browser sync
        if parsed.path == "/api/session/register":
            token = body.get("token", "").strip()
            user_info = body.get("user") or {}
            client_ip = self.client_address[0]
            if token:
                ACTIVE_LAN_SESSIONS[client_ip] = {
                    "token": token,
                    "user": user_info,
                    "timestamp": time.time()
                }
                try:
                    state.log("SUCCESS", f"[AUTH] Da lien ket phien KTV cho IP: {client_ip}")
                except Exception:
                    pass
                self._send_json({"success": True, "message": f"Đã kết nối phiên cho IP {client_ip}"})
            else:
                self._send_json({"success": False, "message": "Thiếu mã token"})
            return

        # 0.1 Đăng nhập trực tiếp TTS từ Dashboard (Bước 1: Username & Password)
        elif parsed.path == "/api/login":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()

            from services.auth_tts import authenticate_tts_step1
            result = authenticate_tts_step1(username, password)

            if result.get("success"):
                client_ip = self.client_address[0]
                token = result.get("token", "")
                user_info = result.get("user", {})
                ACTIVE_LAN_SESSIONS[client_ip] = {
                    "token": token,
                    "user": user_info,
                    "timestamp": time.time()
                }
                if token:
                    save_cached_auth(token, user_info)
                user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or username
                try:
                    state.log("SUCCESS", f"🔑 [XÁC THỰC] {user_display} (IP: {client_ip}) đã đăng nhập TTS thành công!")
                except Exception:
                    pass
                self._send_json({
                    "success": True,
                    "token": token,
                    "user": user_info
                })
            elif result.get("otp_required"):
                self._send_json({
                    "success": False,
                    "otp_required": True,
                    "session_id": result.get("session_id"),
                    "username": result.get("username", username),
                    "phone": result.get("phone", ""),
                    "message": result.get("message", "Vui lòng nhập mã OTP để tiếp tục.")
                })
            else:
                self._send_json({
                    "success": False,
                    "error": result.get("error", "Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản hoặc mật khẩu.")
                })
            return

        # 0.2 Xác thực mã OTP TTS (Bước 2)
        elif parsed.path == "/api/login/otp":
            session_id = body.get("session_id", "").strip()
            otp_code = body.get("otp", "").strip()

            from services.auth_tts import authenticate_tts_step2_otp
            result = authenticate_tts_step2_otp(session_id, otp_code)

            if result.get("success"):
                client_ip = self.client_address[0]
                token = result.get("token", "")
                user_info = result.get("user", {})
                ACTIVE_LAN_SESSIONS[client_ip] = {
                    "token": token,
                    "user": user_info,
                    "timestamp": time.time()
                }
                if token:
                    save_cached_auth(token, user_info)
                user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or "KTV"
                try:
                    state.log("SUCCESS", f"🔑 [XÁC THỰC OTP] {user_display} (IP: {client_ip}) đã qua bước OTP thành công!")
                except Exception:
                    pass
                self._send_json({
                    "success": True,
                    "token": token,
                    "user": user_info
                })
            else:
                client_ip = self.client_address[0]
                err_msg = result.get("error", "Xác thực OTP thất bại. Vui lòng thử lại.")
                try:
                    state.log("ERROR", f"❌ [XÁC THỰC OTP THẤT BÀI] IP {client_ip}: {err_msg}")
                except Exception:
                    pass
                self._send_json({
                    "success": False,
                    "error": err_msg
                })
            return

        # 1. Bật tự động
        elif parsed.path == "/api/start":
            state.is_running = True
            state.stop_requested = False
            if "scan_scopes" in body:
                state.scan_scopes = list(body["scan_scopes"])
            if "auto_close_mode" in body:
                state.auto_close_mode = str(body["auto_close_mode"]).strip()
                state.auto_close = (state.auto_close_mode != "none")
            elif "auto_close" in body:
                state.auto_close = bool(body["auto_close"])
                state.auto_close_mode = "all" if state.auto_close else "none"

            if "interval_minutes" in body:
                state.interval_minutes = int(body["interval_minutes"])

            engine = body.get("engine", getattr(state, "engine", "api"))
            state.engine = engine

            state.status_message = "Đã khởi động tiến trình quét tự động."
            state.log("INFO", f"🚀 Khởi động chu kỳ quét tự động! Phạm vi: {state.scan_scopes} | Chế độ đóng phiếu: [{state.auto_close_mode}] | Lặp: {state.interval_minutes} phút")
            self._send_json({"success": True, "scan_scopes": state.scan_scopes, "auto_close_mode": state.auto_close_mode, "auto_close": state.auto_close})

        # 1.1. Cập nhật cấu hình (Phạm vi quét, Chế độ đóng phiếu, v.v.)
        elif parsed.path == "/api/config":
            if "scan_scopes" in body:
                state.scan_scopes = list(body["scan_scopes"])
                state.log("INFO", f"⚙️ Đã cập nhật phạm vi quét: {state.scan_scopes}")
            if "auto_close_mode" in body:
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
            self._send_json({"success": True, "scan_scopes": getattr(state, "scan_scopes", []), "auto_close_mode": getattr(state, "auto_close_mode", "all"), "auto_close": state.auto_close})

        # 2. Dừng tự động
        elif parsed.path == "/api/stop":
            state.stop_requested = True
            state.is_running = False
            state.log("WARN", "⏹️ DỪNG VÒNG LẶP TỰ ĐỘNG.")
            self._send_json({"success": True})

        # 3. Quét ngay (Theo các phạm vi đã chọn)
        elif parsed.path == "/api/run-now":
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                scopes = body.get("scan_scopes") or getattr(state, "scan_scopes", ["tts_old_data", "tts_new_data"])
                if not scopes:
                    scopes = ["tts_old_data"]
                if state.is_running:
                    state.trigger_now_requested = True
                    state.log("INFO", f"⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC! (Phạm vi: {', '.join(scopes)})")
                    self._send_json({"success": True})
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
                                    from services.tts_old_api_voice import execute_tts_old_api_voice_cycle
                                    execute_tts_old_api_voice_cycle()
                                elif sc == "tts_new_data":
                                    from services.tts_new_data import execute_tts_new_data_cycle
                                    execute_tts_new_data_cycle()
                                elif sc == "tts_new_voice":
                                    from services.tts_new_voice import execute_tts_new_voice_cycle
                                    execute_tts_new_voice_cycle()
                        except Exception as ex_m:
                            state.log("ERROR", f"Lỗi thực thi quét theo yêu cầu: {ex_m}")
                        finally:
                            state.status = "IDLE"
                            state.status_message = "Hoàn tất quét theo yêu cầu."
                    
                    threading.Thread(target=_run_scopes_manual, args=(scopes,), daemon=True).start()
                    self._send_json({"success": True, "message": "Đã kích hoạt quét ngay các phạm vi đã chọn."})

        # 4. Quét TTS Cũ (Thoại / SMS / Gói)
        elif parsed.path == "/api/tts_old/scan_voice":
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_old_voice_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đang tiến hành quét riêng phiếu Thoại / SMS từ TTS Cũ..."})

        # 5. Quét TTS Mới (Mobile Internet)
        elif parsed.path == "/api/ttsnew/run-now":
            state.engine = "tts_new"
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                if state.is_running:
                    state.trigger_now_requested = True
                    state.log("INFO", "⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC (TTS MỚI - DATA)!")
                    self._send_json({"success": True, "message": "Đã kích hoạt quét ngay chu kỳ TTS Mới..."})
                else:
                    threading.Thread(target=execute_tts_new_data_cycle, daemon=True).start()
                    self._send_json({"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Mới..."})

        # 6. Quét TTS Mới (Thoại / SMS / Gói)
        elif parsed.path == "/api/ttsnew/scan_voice":
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_new_voice_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đang tiến hành quét phiếu Thoại / SMS từ TTS Mới..."})

        # 7. Mở chi tiết phiếu trên TTS Mới (chi-tiet-phieu-pakh)
        elif parsed.path == "/api/ttsnew/open_detail":
            ticket_code = str(body.get("ticket_code") or "").strip()
            phone = str(body.get("phone") or "").strip()
            incident_time = str(body.get("incident_time") or "").strip()

            conn = get_db_connection()
            row = None
            if ticket_code:
                row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan FROM tickets WHERE ticket_code = ? OR ticket_code LIKE ?", (ticket_code, f"{ticket_code}%")).fetchone()
            if not row and phone:
                row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan FROM tickets WHERE phone = ? AND source = 'tts_new'", (phone,)).fetchone()
            conn.close()

            ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
            flow_id = row["flow_id"] if (row and row["flow_id"]) else None
            code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
            clean_code = code.split("\n")[0].strip() if code else ""
            comment_val = str(row["comment"] or "").strip() if (row and "comment" in row.keys()) else ""
            action_plan_val = str(row["action_plan"] or "").strip() if (row and "action_plan" in row.keys()) else ""

            if not ticket_id and clean_code and "/" in clean_code:
                try:
                    ticket_id = int(clean_code.split("/")[-1])
                except Exception:
                    pass

            if not flow_id:
                try:
                    from ttsnew_api import extract_token_from_browser, fetch_active_tickets
                    tok = extract_token_from_browser()
                    if tok:
                        active_t = fetch_active_tickets(tok, limit=1000)
                        for at in active_t:
                            tc = at.get("ticketCode")
                            if tc == code or tc == clean_code or (ticket_id and at.get("ticketId") == ticket_id):
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

            state.log("STEP", f"🌐 Đang mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới...")

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

                    # Đợi trang chi tiết tải xong và tự động mở cửa sổ "Cập nhật xử lý"
                    try:
                        btn_cap_nhat = target_page.wait_for_selector('button.p-button-primary:has-text("Cập nhật xử lý")', timeout=10000)
                        if btn_cap_nhat:
                            btn_cap_nhat.click()
                            target_page.wait_for_timeout(1200)

                            # Tự động điền B0: True, Cả ô "Nội dung xử lý" và "Nội dung chuyển giao" đều là Cột 10 + 11
                            dialog = target_page.query_selector('.p-dialog:has-text("Cập nhật xử lý")')
                            if dialog:
                                # B0: True
                                b0_true = dialog.query_selector('p-radiobutton:has-text("True") .p-radiobutton-box')
                                if b0_true:
                                    b0_true.click()

                                # Nội dung kết hợp Cột 10 (Nội dung phân tích) + Cột 11 (Nội dung phản hồi/phương án)
                                combined_text = f"{comment_val}\n{action_plan_val}".strip() if (comment_val and action_plan_val) else (comment_val or action_plan_val or "")

                                # Điền vào ô "Nội dung xử lý"
                                if combined_text:
                                    txt_closing = dialog.query_selector('textarea[name="closingContent"], textarea[formcontrolname="closingContent"]')
                                    if txt_closing:
                                        txt_closing.fill(combined_text)

                                # Điền vào ô "Nội dung chuyển giao"
                                if combined_text:
                                    txt_assign = dialog.query_selector('textarea[name="assignContent"], textarea[formcontrolname="assignContent"]')
                                    if txt_assign:
                                        txt_assign.fill(combined_text)
                    except Exception as ex_modal:
                        state.log("WARN", f"Chưa tự động bật được nút Cập nhật xử lý: {ex_modal}")

                state.log("SUCCESS", f"✅ Đã mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới!")
                self._send_json({
                    "success": True, 
                    "message": f"Đã mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới", 
                    "ticket_code": code,
                    "ticket_id": ticket_id,
                    "flow_id": flow_id
                })
            except Exception as ex_open:
                state.log("WARN", f"⚠️ Lỗi mở tab TTS Mới: {ex_open}")
                self._send_json({"success": False, "message": f"Lỗi mở tab TTS Mới: {str(ex_open)}"})

        # 7.1. Đóng / chuyển bước 1 phiếu trên TTS Mới (Quy trình 2 vòng)
        elif parsed.path == "/api/ttsnew/close_one":
            phone = str(body.get("phone") or "").strip()
            ticket_code = str(body.get("ticket_code") or "").strip()
            comment_custom = str(body.get("comment") or "").strip()
            action_plan_custom = str(body.get("action_plan") or "").strip()

            conn = get_db_connection()
            row = None
            if ticket_code:
                row = conn.execute("SELECT * FROM tickets WHERE ticket_code = ? OR ticket_code LIKE ?", (ticket_code, f"{ticket_code}%")).fetchone()
            if not row and phone:
                row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND source = 'tts_new'", (phone,)).fetchone()
            conn.close()

            ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
            flow_id = row["flow_id"] if (row and row["flow_id"]) else None
            code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
            clean_code = code.split("\n")[0].strip() if code else ""
            status_val = str(row["status"] or "") if row else ""
            comment_val = comment_custom or (str(row["comment"] or "").strip() if row else "")
            action_plan_val = action_plan_custom or (str(row["action_plan"] or "").strip() if row else "")

            # Kiểm tra THÔNG TIN MỞ LẠI TTS: Nếu số lần mở lại > 0, cần cờ force từ KTV
            reopen_cnt = int(row["reopen_count"] or 0) if (row and "reopen_count" in row.keys()) else 0
            force_close = body.get("force", False)
            if reopen_cnt > 0 and not force_close:
                self._send_json({
                    "success": False, 
                    "is_reopened": True,
                    "reopen_count": reopen_cnt,
                    "message": f"⚠️ Phiếu này đã mở lại {reopen_cnt} lần (THÔNG TIN MỞ LẠI TTS). Hệ thống chặn tự động đóng. KTV cần xác nhận trước khi đóng thủ công."
                })
                return

            from ttsnew_api import extract_token_from_browser, fetch_active_tickets, api_transfer_ttsnew_ticket
            tok = extract_token_from_browser()
            if not tok:
                self._send_json({"success": False, "message": "Không tìm thấy Bearer Token của TTS Mới. Hãy mở tab tts.vnptnet.vn."})
                return

            try:
                raw_active = fetch_active_tickets(tok, limit=1000)
                for r_it in raw_active:
                    if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
                       (clean_code and str(r_it.get("ticketCode")) == str(clean_code)) or \
                       (phone and phone in str(r_it)):
                        flow_id = r_it.get("id")
                        ticket_id = r_it.get("ticketId")
                        break
            except Exception:
                pass

            if not flow_id or not ticket_id:
                self._send_json({"success": False, "message": f"Không tìm thấy luồng xử lý (flow_id/ticket_id) của phiếu {clean_code or phone} trên TTS Mới."})
                return

            res_close = api_transfer_ttsnew_ticket(
                token=tok,
                ticket_flow_id=flow_id,
                ticket_id=ticket_id,
                phone=phone or (row["phone"] if row else ""),
                ticket_code=clean_code,
                status=status_val,
                closing_content=comment_val,
                assign_content=action_plan_val
            )
            if not res_close.get("success"):
                err_msg = res_close.get("message", "Lỗi chuyển bước")
                state.log("WARN", f"⚠️ [Phiếu lỗi] Phiếu {clean_code} ({phone}) không đóng được: {err_msg}")
                try:
                    conn = get_db_connection()
                    target_phone = phone or (row["phone"] if row else "")
                    conn.execute("""
                        UPDATE tickets 
                        SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                        WHERE (ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                    """, (f"{clean_code}%", target_phone))
                    conn.commit()
                    conn.close()
                except Exception as ex_db:
                    pass
            self._send_json(res_close)

        # 7.2. Tự động đóng hàng loạt phiếu TTS Mới (Quy trình 2 vòng)
        elif parsed.path == "/api/ttsnew/close_all":
            from ttsnew_api import extract_token_from_browser, fetch_active_tickets, filter_data_tickets, api_transfer_ttsnew_ticket
            tok = extract_token_from_browser()
            if not tok:
                self._send_json({"success": False, "message": "Không tìm thấy token TTS Mới."})
                return

            def _run_close_all():
                state.log("STEP", "🚀 Bắt đầu tự động chuyển bước/đóng tất cả phiếu TTS Mới đủ điều kiện...")
                try:
                    raw = fetch_active_tickets(tok, limit=1000)
                    data_tickets = filter_data_tickets(raw)
                    conn = get_db_connection()
                    total_success = 0
                    for it in data_tickets:
                        flow_id = it.get("id")
                        ticket_id = it.get("ticketId")
                        ticket_code = it.get("ticketCode")
                        row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? OR ticket_code = ? OR ticket_code LIKE ?", 
                                           (ticket_id, ticket_code, f"{ticket_code}%")).fetchone()
                        if row and row["status"]:
                            # Kiểm tra THÔNG TIN MỞ LẠI TTS
                            rc = int(row["reopen_count"] or 0) if "reopen_count" in row.keys() else 0
                            if rc > 0:
                                state.log("WARN", f"   ↳ ⛔ Bỏ qua {ticket_code} ({row['phone']}): Đã mở lại {rc} lần (THÔNG TIN MỞ LẠI TTS) - KHÔNG ĐÓNG TỰ ĐỘNG!")
                                continue

                            from db_manager import check_ticket_can_close
                            can_close, reason = check_ticket_can_close(dict(row))
                            if not can_close:
                                state.log("INFO", f"   ↳ ⏸️ Giữ nguyên {ticket_code} ({row['phone']}): Chưa đủ điều kiện đóng ({reason})")
                                continue

                            res = api_transfer_ttsnew_ticket(
                                token=tok,
                                ticket_flow_id=flow_id,
                                ticket_id=ticket_id,
                                phone=row["phone"],
                                ticket_code=ticket_code,
                                status=row["status"],
                                closing_content=row["comment"] or "",
                                assign_content=row["action_plan"] or ""
                            )
                            if res.get("success"):
                                total_success += 1
                                state.log("SUCCESS", f"   ↳ [{total_success}] {res.get('message')}")
                            else:
                                state.log("WARN", f"   ↳ ⚠️ [Phiếu lỗi] {ticket_code}: {res.get('message')}")
                                try:
                                    conn.execute("""
                                        UPDATE tickets 
                                        SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                                        WHERE (ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                                    """, (f"{ticket_code}%", row["phone"]))
                                    conn.commit()
                                except Exception:
                                    pass
                    conn.close()
                    state.log("SUCCESS", f"🎉 Hoàn thành xử lý {total_success}/{len(data_tickets)} phiếu TTS Mới!")
                except Exception as ex_all:
                    state.log("ERROR", f"Lỗi khi đóng hàng loạt phiếu TTS Mới: {ex_all}")

            threading.Thread(target=_run_close_all, daemon=True).start()
            self._send_json({"success": True, "message": "Đang tiến hành tự động chuyển bước/đóng hàng loạt phiếu TTS Mới..."})

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
                from auth_extractor import get_chrome_debug_driver
                driver = get_chrome_debug_driver()

                sapc_client = None
                try:
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

                cell_desc = info_res.get("Cell ID") or info_res.get("ECGI") or "--"
                rat = info_res.get("Radio") or "Sóng di động"

                conn = get_db_connection()
                with conn:
                    cur = conn.execute("SELECT package_title, ticket_content FROM tickets WHERE phone = ?", (phone,))
                    row = cur.fetchone()
                    pkg_title = (row[0] if row else "Thoại / SMS") or ""
                    t_content = row[1] if row else ""

                    num_file = BASE_DIR / "number" / f"{phone}.json"
                    existing_clean_data = []
                    if num_file.exists():
                        try:
                            with open(num_file, "r", encoding="utf-8") as nf:
                                ndata = json.load(nf)
                                existing_clean_data = ndata.get("btools_technical_data") or ndata.get("data") or []
                        except Exception:
                            pass

                    is_mobile_data = "thoại" not in str(pkg_title).lower() and "sms" not in str(pkg_title).lower()

                    # Nếu là Mobile Internet -> Cào BTools mới nhất để cập nhật data usage
                    if is_mobile_data:
                        try:
                            from crawler_btools import extract_btools_single_phone
                            from data_processor import standardize_btools_data
                            today = datetime.today()
                            start_d = (today - timedelta(days=4)).strftime("%Y-%m-%d")
                            end_d = today.strftime("%Y-%m-%d")
                            raw_bt = extract_btools_single_phone(driver, phone, start_d, end_d)
                            if raw_bt:
                                existing_clean_data = standardize_btools_data(raw_bt)
                                with open(num_file, "w", encoding="utf-8") as nf:
                                    json.dump({
                                        "phone": phone,
                                        "package_title": pkg_title,
                                        "ticket_content": t_content,
                                        "btools_technical_data": existing_clean_data,
                                        "data": existing_clean_data
                                    }, nf, ensure_ascii=False, indent=2)
                        except Exception as ex_bt_pre:
                            state.log("WARN", f"Lỗi cào BTools khi tiền kiểm {phone}: {ex_bt_pre}")

                    # Trích xuất gói cước phát sinh từ BTools
                    cfg_p = BASE_DIR / "diagnostic_config.json"
                    ex_codes = set()
                    if cfg_p.exists():
                        try:
                            with open(cfg_p, "r", encoding="utf-8") as cf:
                                ex_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
                        except Exception:
                            pass
                    real_pkgs = set()
                    for r in (existing_clean_data or []):
                        sc = str(r.get("SERVICE_ID_CODE", "") or r.get("SERVICE_ID", "")).strip()
                        sn = str(r.get("SERVICE_NAME", "")).strip()
                        if sc.lower() and sc.lower() not in ex_codes and sc.lower() not in ("null", "none"):
                            if sn and "gói cước lạ" not in sn.lower() and sn.lower() not in ex_codes and sn.lower() not in ("null", "none"):
                                real_pkgs.add(sn)
                            elif sc.lower() not in ("null", "none"):
                                real_pkgs.add(sc)
                    real_pkgs_str = ", ".join(list(real_pkgs)) if real_pkgs else "Không phát sinh gói TM"
                    formatted_pkg = get_formatted_sapc_packages(phone, fallback_btools=real_pkgs_str)

                    cem_desc = (f"Không có dữ liệu CEM (5 ngày) [Cell HSS: {cell_desc}]" if cell_desc and cell_desc != "--" else "Không có dữ liệu CEM (5 ngày)")
                    app_usage_str = "--"
                    cem_recs = []
                    app_evs = []
                    if is_mobile_data:
                        try:
                            from cem_client import CEMClient, save_cem_data_to_file
                            cem_client = CEMClient(driver=driver)
                            cem_recs = cem_client.get_subscriber_history_5days(phone, days=5)
                            if cem_recs:
                                cem_desc = CEMClient.extract_top_cells_summary(cem_recs)
                            app_evs = cem_client.get_subscriber_app_events(phone, days=5)
                            if app_evs:
                                app_usage_str = CEMClient.extract_top_apps_summary(app_evs)
                            save_cem_data_to_file(phone, cem_recs, app_evs, base_dir=BASE_DIR)
                        except Exception as ex_c:
                            state.log("WARN", f"Lỗi tra cứu CEM khi tiền kiểm tra {phone}: {ex_c}")

                    if is_mobile_data:
                        status_calc, comment_calc, action_calc, _ = analyze_subscriber_status(
                            existing_clean_data, pkg_title, t_content, phone_84=phone,
                            cem_records=cem_recs, app_events=app_evs, incident_time_str=incident_time, driver=driver
                        )
                    else:
                        status_calc = ""
                        comment_calc = ""
                        action_calc = ""

                    conn.execute("""
                        UPDATE tickets 
                        SET real_packages = ?, 
                            rat_types = ?,
                            cem_data = ?,
                            app_usage = CASE WHEN ? != '--' THEN ? ELSE app_usage END,
                            status = ?,
                            comment = ?,
                            action_plan = ?,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE phone = ?
                    """, (formatted_pkg, rat, cem_desc, app_usage_str, app_usage_str, status_calc, comment_calc, action_calc, phone))
                conn.close()

                state.log("SUCCESS", f"✅ Đã tiền kiểm Core xong cho {phone}: Radio={info_res.get('Radio')}, HSS={info_res.get('HSS Profile')}, IP={info_res.get('IPv4')}, NAM={info_res.get('NAM')}")
                self._send_json({"success": True, "formatted_pkg": formatted_pkg, "info": info_res})
            except Exception as ex_pre:
                state.log("WARN", f"⚠️ Lỗi tiền kiểm tra cho {phone}: {ex_pre}")
                self._send_json({"success": False, "error": str(ex_pre)})

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
            state.log("WARN", f"🗑️ ĐÃ XÓA DỮ LIỆU BẢNG TẠM {sys_text.upper()}.")
            self._send_json({"success": True})

        # 12. Quét TTS Cũ (Mobile Internet)
        elif parsed.path == "/api/tts_old_api/run-now":
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                state.engine = "api"
                if state.is_running:
                    state.trigger_now_requested = True
                    state.log("INFO", "⚡ KÍCH HOẠT QUÉT NGAY LẬP TỨC (TTS CŨ - DATA)!")
                    self._send_json({"success": True, "message": "Đã kích hoạt quét ngay chu kỳ mới!"})
                else:
                    threading.Thread(target=execute_tts_old_api_data_cycle, daemon=True).start()
                    self._send_json({"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Cũ (Data)..."})

        # 13. Quét TTS Cũ (Thoại / SMS / Gói)
        elif parsed.path == "/api/tts_old_api/scan_voice":
            if state.status == "PROCESSING":
                self._send_json({"success": False, "message": "Hệ thống đang bận thực hiện chu kỳ khác."})
            else:
                threading.Thread(target=execute_tts_old_api_voice_cycle, daemon=True).start()
                self._send_json({"success": True, "message": "Đã kích hoạt quét tiền kiểm TTS Cũ (Thoại/SMS)..."})

        # 14. Đóng thủ công 1 phiếu TTS Cũ
        elif parsed.path in ("/api/tts_old_api/close_one", "/api/tickets/close_one"):
            phone = body.get("phone")
            incident_time = body.get("incident_time")
            comment_input = body.get("comment")
            action_plan_input = body.get("action_plan")
            if not phone:
                self.send_error(400, "Missing phone")
                return

            conn = get_db_connection()
            row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND incident_time = ?", (phone, incident_time)).fetchone()
            conn.close()

            if not row:
                self._send_json({"success": False, "message": f"Không tìm thấy phiếu của SĐT {phone} trong cơ sở dữ liệu."})
                return

            ticket_dict = dict(row)
            if not ticket_dict.get("id_yeu_cau") and ticket_dict.get("flow_id"):
                ticket_dict["id_yeu_cau"] = ticket_dict["flow_id"]
            if not ticket_dict.get("ma_ccos") and ticket_dict.get("ticket_code"):
                ticket_dict["ma_ccos"] = ticket_dict["ticket_code"]

            if comment_input is not None:
                update_ticket_field(phone, "comment", comment_input, incident_time=incident_time)
                ticket_dict["comment"] = comment_input
            if action_plan_input is not None:
                update_ticket_field(phone, "action_plan", action_plan_input, incident_time=incident_time)
                ticket_dict["action_plan"] = action_plan_input

            client_token = (body.get("token") or "").strip()
            client_user_id = body.get("user_id")
            client_user_name = (body.get("user_name") or "").strip()

            token = client_token
            user_id = client_user_id
            user_name = client_user_name

            if not token:
                token, user_info = extract_token_from_browser()
                if user_info:
                    user_id = user_id or user_info.get("Id") or user_info.get("id") or 0
                    user_name = user_name or user_info.get("HoTen") or user_info.get("TaiKhoan") or "Quản trị viên"

            if not token:
                self._send_json({"success": False, "message": "Không tìm thấy token scnntttoken của TTS Cũ. Vui lòng kết nối tài khoản TTS trước."})
                return

            if not user_name:
                user_name = "Kỹ thuật viên"

            user_id = user_id or 0
            nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)

            import update_tts.config as tts_config
            import update_tts.excel_reader as excel_reader
            matched_nn, action_override = excel_reader.get_nguyen_nhan_and_action(ticket_dict)

            id_nn = None
            if matched_nn:
                id_nn = nguyen_nhan_map.get(matched_nn.lower()) or nguyen_nhan_map.get(matched_nn)
            if not id_nn:
                id_nn = 1016  # Mạng lưới đảm bảo, KH sử dụng bình thường

            action_text = ticket_dict.get('action_plan', '') or action_override or ''
            full_content = f"{ticket_dict.get('comment', '')}\n{action_text}".strip()
            if not full_content:
                full_content = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"

            state.log("STEP", f"Đang gửi request đóng phiếu TTS Cũ cho SĐT {phone} bởi [{user_name}]...")
            ok, msg = close_tts_old_ticket_api(
                ticket=ticket_dict,
                id_nguyen_nhan=id_nn,
                noi_dung=full_content,
                token=token,
                user_id=user_id,
                dry_run=False
            )
            if ok:
                update_ticket_field(phone, "ticket_status", "Đã đóng", incident_time=incident_time)
                update_ticket_field(phone, "closed_by", user_name, incident_time=incident_time)
                state.closed_count += 1
                state.log("SUCCESS", f"✅ [{user_name}] {msg}")
            else:
                state.log("WARN", msg)

            self._send_json({"success": ok, "message": msg, "closed_by": user_name})

        else:
            self.send_error(404, "Not Found")


# ==============================================================================
# QUẢN LÝ TIẾN TRÌNH VÀ TRÌNH DUYỆT
# ==============================================================================
def kill_existing_port_process(port: int):
    """Đảm bảo không có tiến trình zombie cũ nào chiếm port trước khi bind."""
    try:
        current_pid = os.getpid()
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        for line in output.strip().splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = int(parts[-1])
                if pid != current_pid and pid > 0:
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        print(f"⚠️ Đã giải phóng tiến trình cũ (PID: {pid}) đang chiếm port {port}.")
                    except Exception:
                        pass
    except Exception:
        pass


def launch_chrome_debug():
    """Kiểm tra Chrome Debugging (port 9222) nếu có sẵn thì thông báo, không ép buộc mở Chrome."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        if res == 0:
            print("✅ Chrome Debugging (Port 9222) đã sẵn sàng.")
            return True
    except Exception:
        pass
    return False


def open_in_chrome_debug(url):
    """Kích hoạt URL nếu đang có phiên Chrome Debugging mở."""
    try:
        import requests
        tabs_res = requests.get("http://127.0.0.1:9222/json/list", timeout=0.5)
        if tabs_res.status_code == 200:
            tabs = tabs_res.json()
            for t in tabs:
                if f":{PORT}" in t.get("url", ""):
                    requests.get(f"http://127.0.0.1:9222/json/activate/{t.get('id')}", timeout=0.5)
                    return
            requests.get(f"http://127.0.0.1:9222/json/new?{url}", timeout=0.5)
            return
    except Exception:
        pass


class RobustThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        exc_type, _, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        super().handle_error(request, client_address)


# ==============================================================================
# KHỞI CHẠY MÁY CHỦ WEB DASHBOARD
# ==============================================================================
def run_dashboard():
    kill_existing_port_process(PORT)
    init_db()
    launch_chrome_debug()

    # Khởi chạy luồng lặp tự động nền
    worker_thread = threading.Thread(target=automation_worker_loop, daemon=True)
    worker_thread.start()

    RobustThreadingHTTPServer.allow_reuse_address = True
    server = RobustThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
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
