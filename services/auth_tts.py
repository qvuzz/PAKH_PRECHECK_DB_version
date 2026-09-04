# services/auth_tts.py
# Module xác thực tài khoản TTS VNPT trực tiếp từ Dashboard, hỗ trợ 2FA / OTP
# SỬ DỤNG DEDICATED WORKER THREAD để đảm bảo Playwright luôn chạy trên cùng 1 thread
# loại bỏ triệt để lỗi greenlet: "cannot switch to a different thread"

import time
import json
import uuid
import base64
import queue
import threading
from playwright.sync_api import sync_playwright

_JOB_QUEUE = queue.Queue()
_WORKER_THREAD = None
_WORKER_LOCK = threading.Lock()


def _ensure_worker_started():
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = threading.Thread(target=_auth_worker_loop, daemon=True, name="PlaywrightAuthWorker")
            _WORKER_THREAD.start()


def _decode_user_str(user_str: str) -> dict:
    if not user_str:
        return {}
    try:
        data = json.loads(user_str)
    except Exception:
        try:
            decoded = base64.b64decode(user_str).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
        except Exception:
            return {}
    if isinstance(data, dict):
        if "userInfo" in data and isinstance(data["userInfo"], dict):
            return data["userInfo"]
        return data
    return {}


def _find_otp_input(page):
    """
    Tìm ô nhập mã OTP trên giao diện CAS với nhiều chiến lược dự phòng.
    """
    candidates = [
        "input#otp", "input[name='otp']",
        "input#token", "input[name='token']",
        "input#code", "input[name='code']",
        "input#passcode", "input[name='passcode']",
        "input[name='otpToken']", "input[name='smsCode']",
        "input[name='credential']", "input[name='twoFactorCode']",
        "input[placeholder*='OTP' i]", "input[placeholder*='otp' i]",
        "input[placeholder*='mã' i]", "input[placeholder*='Mã' i]",
    ]
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            pass

    # Tìm tất cả input có thể nhập liệu không phải username
    try:
        all_inputs = page.query_selector_all("input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio'])")
        for inp in all_inputs:
            try:
                inp_id = (inp.get_attribute("id") or "").lower()
                inp_name = (inp.get_attribute("name") or "").lower()
                if "username" in inp_id or "username" in inp_name:
                    continue
                if inp.is_visible():
                    return inp
            except Exception:
                pass
    except Exception:
        pass

    return None


def _submit_otp_form(page, otp_input):
    """
    Bấm nút Đăng nhập / Xác nhận trên màn hình OTP hoặc submit form.
    """
    btn_candidates = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('ĐĂNG NHẬP')",
        "button:has-text('Đăng nhập')",
        "input[value*='ĐĂNG NHẬP']",
        "input[value*='Đăng nhập']",
        "input[value*='LOGIN']",
        "button:has-text('Xác nhận')",
        "button:has-text('Tiếp tục')",
        "#submit",
        ".btn-submit",
        "form button",
        "form input[type='button']",
    ]
    for b_sel in btn_candidates:
        try:
            b = page.query_selector(b_sel)
            if b and b.is_visible():
                b.click()
                return True
        except Exception:
            pass

    # Thử Enter trên input
    if otp_input:
        try:
            otp_input.press("Enter")
            return True
        except Exception:
            pass

    # Thử submit form trực tiếp bằng JS
    try:
        page.evaluate("() => { const f = document.querySelector('form'); if (f) f.submit(); }")
        return True
    except Exception:
        pass

    return False


def _worker_step1(browser, active_sessions: dict, username: str, password: str, timeout: int = 15) -> dict:
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        return {"success": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu TTS."}

    session_id = str(uuid.uuid4())

    try:
        context = browser.new_context()
        page = context.new_page()

        # 1. Mở trang đăng nhập TTS
        try:
            page.goto("https://tts.vnpt.vn/", timeout=18000)
        except Exception as ex:
            context.close()
            return {"success": False, "error": f"Không thể kết nối máy chủ TTS VNPT: {ex}"}

        # 2. Đợi form đăng nhập
        try:
            page.wait_for_selector("#username", timeout=8000)
        except Exception:
            tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
            if tok:
                u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                context.close()
                return {"success": True, "token": tok, "user": _decode_user_str(u_str)}
            context.close()
            return {"success": False, "error": "Không tìm thấy form đăng nhập TTS."}

        # 3. Điền tài khoản và mật khẩu
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("button[type='submit']")

        # 4. Chờ xem kết quả: Lỗi mật khẩu, Cần OTP, hay Đăng nhập thành công ngay
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.5)

            # A. Kiểm tra thông báo lỗi từ CAS
            try:
                curr_url = page.url.lower()
                if "cas/login" in curr_url or "login" in curr_url:
                    alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert']")
                    for a in alerts:
                        if a.is_visible():
                            txt = a.inner_text().strip()
                            if "không thành công" in txt.lower() or "kiểm tra tên đăng nhập" in txt.lower():
                                context.close()
                                return {"success": False, "error": "Sai tên đăng nhập hoặc mật khẩu TTS!"}
                            if "khóa" in txt.lower() or "lock" in txt.lower():
                                context.close()
                                return {"success": False, "error": f"Tài khoản bị khóa: {txt}"}
            except Exception:
                pass

            # B. Kiểm tra nếu đã có token ngay (không bị yêu cầu OTP)
            try:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    context.close()
                    return {
                        "success": True,
                        "token": tok,
                        "user": _decode_user_str(u_str) or {"TaiKhoan": username, "HoTen": username}
                    }
            except Exception:
                pass

            # C. Kiểm tra nếu hệ thống chuyển sang màn hình yêu cầu OTP / 2FA
            try:
                curr_url = page.url.lower()
                content = page.content().lower()
                has_otp_in_url = any(k in curr_url for k in ["otp", "twofactor", "verify"])
                has_otp_in_text = any(k in content for k in ["mã otp", "mã xác thực", "xác thực otp", "nhập mã"])
                has_otp_input = bool(page.query_selector("input#otp, input[name='otp'], input#token, input[name='token'], input[placeholder*='OTP'], input[placeholder*='otp']"))

                if has_otp_in_url or has_otp_in_text or has_otp_input:
                    # Trích xuất số điện thoại nếu có
                    import re
                    phone = ""
                    pm = re.search(r'(0\d{9,10}|\d{4}\*{3}\d{3})', content)
                    if pm:
                        phone = pm.group(0)

                    # Lưu phiên để chờ người dùng nhập OTP
                    active_sessions[session_id] = {
                        "context": context,
                        "page": page,
                        "username": username,
                        "phone": phone,
                        "created_at": time.time()
                    }
                    print(f"[AuthWorker] Đã tạo phiên chờ OTP: {session_id[:8]} cho user: {username}")
                    return {
                        "success": False,
                        "otp_required": True,
                        "session_id": session_id,
                        "username": username,
                        "phone": phone,
                        "message": f"Mã xác thực OTP của bạn hiện đã được gửi đến số điện thoại: {phone}" if phone else "Mã xác thực OTP đã được gửi đến số điện thoại của bạn."
                    }
            except Exception:
                pass

        # Hết thời gian chờ mà chưa có token cũng chưa phát hiện OTP
        active_sessions[session_id] = {
            "context": context,
            "page": page,
            "username": username,
            "created_at": time.time()
        }
        return {
            "success": False,
            "otp_required": True,
            "session_id": session_id,
            "message": "Vui lòng nhập mã OTP để hoàn tất đăng nhập."
        }

    except Exception as ex:
        return {"success": False, "error": f"Lỗi hệ thống đăng nhập: {str(ex)}"}


def _worker_step2(active_sessions: dict, session_id: str, otp_code: str, timeout: int = 25) -> dict:
    session = active_sessions.get(session_id)
    if not session:
        return {"success": False, "error": "Phiên đăng nhập đã hết hạn hoặc không tồn tại. Vui lòng bấm Đăng nhập lại."}

    page = session["page"]
    context = session["context"]
    username = session["username"]
    otp_code = (otp_code or "").strip()

    print(f"[OTP Step 2] Bắt đầu xác thực OTP cho user: {username}, session: {session_id[:8]}...")
    print(f"[OTP Step 2] Trang hiện tại: {page.url}")

    try:
        # 1. Tìm ô nhập OTP và điền mã nếu có
        if otp_code:
            otp_input = _find_otp_input(page)
            if otp_input:
                try:
                    inp_name = otp_input.get_attribute("name") or otp_input.get_attribute("id") or "unnamed"
                    print(f"[OTP Step 2] Đã tìm thấy ô nhập OTP ({inp_name}), tiến hành điền: {otp_code}...")
                    otp_input.fill("")
                    otp_input.fill(otp_code)
                    time.sleep(0.3)
                except Exception as ex:
                    print(f"[OTP Step 2] Lỗi khi điền OTP: {ex}")
            else:
                print("[OTP Step 2] CẢNH BÁO: Không tìm thấy ô nhập OTP cụ thể trên trang!")

            # 2. Bấm nút submit
            submitted = _submit_otp_form(page, otp_input)
            print(f"[OTP Step 2] Đã kích hoạt submit: {submitted}")

        # 3. Chờ token xuất hiện trong localStorage / sessionStorage hoặc phát hiện thông báo lỗi
        start_time = time.time()
        token = ""
        user_info = {}
        last_url = page.url

        while time.time() - start_time < timeout:
            time.sleep(0.5)

            # A. Kiểm tra thông báo lỗi từ CAS
            try:
                alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert'], #msg, .error, .text-danger, .has-error")
                for a in alerts:
                    if a.is_visible():
                        txt = a.inner_text().strip()
                        if any(k in txt.lower() for k in ["không đúng", "sai", "hết hạn", "invalid", "thất bại", "không hợp lệ"]):
                            print(f"[OTP Step 2] Phát hiện lỗi CAS: {txt}")
                            return {"success": False, "error": f"Lỗi xác thực: {txt}"}
            except Exception:
                pass

            # B. Kiểm tra URL thay đổi
            try:
                curr_url = page.url.lower()
                if curr_url != last_url:
                    last_url = curr_url
                    print(f"[OTP Step 2] URL chuyển sang: {curr_url}")
            except Exception:
                pass

            # C. Kiểm tra token trong localStorage hoặc sessionStorage
            try:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken') || sessionStorage.getItem('scnntttoken')")
                if tok and len(tok) > 10:
                    token = tok
                    u_str = page.evaluate("() => localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo')")
                    user_info = _decode_user_str(u_str)
                    print(f"[OTP Step 2] Thành công! Đã lấy được token: {token[:15]}...")
                    break
            except Exception:
                # Page có thể đang điều hướng, context bị reset tạm thời
                pass

        if token:
            try:
                context.close()
            except Exception:
                pass
            active_sessions.pop(session_id, None)
            return {
                "success": True,
                "token": token,
                "user": user_info or {"TaiKhoan": username, "HoTen": username}
            }
        else:
            # Lưu snapshot để phân tích nguyên nhân nếu thất bại
            try:
                import os
                os.makedirs("scratch", exist_ok=True)
                page.screenshot(path="scratch/otp_failed_snapshot.png")
                with open("scratch/otp_failed_dom.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"[OTP Step 2] Thất bại - Đã lưu snapshot tại scratch/otp_failed_snapshot.png. URL: {page.url}")
            except Exception as snap_ex:
                print(f"[OTP Step 2] Không thể lưu snapshot: {snap_ex}")

            # Kiểm tra text trong body xem có thông báo lỗi cụ thể
            try:
                body_txt = page.inner_text("body").lower()
                for err_k in ["không đúng", "sai", "hết hạn", "không hợp lệ", "thất bại"]:
                    if err_k in body_txt:
                        return {"success": False, "error": "Mã OTP không chính xác hoặc đã hết hạn. Vui lòng kiểm tra lại."}
            except Exception:
                pass

            return {
                "success": False,
                "error": "Xác thực OTP không thành công hoặc hết thời gian chờ từ máy chủ CAS. Vui lòng thử lại."
            }

    except Exception as ex:
        print(f"[OTP Step 2] Ngoại lệ hệ thống: {ex}")
        return {"success": False, "error": f"Lỗi xử lý xác thực OTP: {str(ex)}"}


def _auth_worker_loop():
    """
    Dedicated worker thread nơi Playwright duy nhất được khởi tạo và chạy.
    Mọi Page, Context, Event Loop đều gắn cố định với thread này.
    """
    print("[AuthWorker] Khởi tạo luồng xử lý Playwright chuyên biệt...")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            active_sessions = {}

            print("[AuthWorker] Playwright Browser đã sẵn sàng nhận lệnh.")
            while True:
                try:
                    # Dọn dẹp session quá hạn (> 180s)
                    now = time.time()
                    expired = [sid for sid, s in active_sessions.items() if now - s.get("created_at", 0) > 180]
                    for sid in expired:
                        s = active_sessions.pop(sid, None)
                        if s and "context" in s:
                            try:
                                s["context"].close()
                            except Exception:
                                pass

                    # Nhận job từ queue
                    try:
                        job = _JOB_QUEUE.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if job is None:
                        break

                    action = job.get("action")
                    args = job.get("args", {})
                    res_q = job.get("res_q")

                    if action == "step1":
                        res = _worker_step1(browser, active_sessions, args.get("username", ""), args.get("password", ""), args.get("timeout", 15))
                        res_q.put(res)
                    elif action == "step2":
                        res = _worker_step2(active_sessions, args.get("session_id", ""), args.get("otp_code", ""), args.get("timeout", 25))
                        res_q.put(res)
                    else:
                        res_q.put({"success": False, "error": f"Hành động không hợp lệ: {action}"})

                except Exception as ex:
                    print(f"[AuthWorker] Ngoại lệ trong vòng lặp worker: {ex}")
    except Exception as fatal_ex:
        print(f"[AuthWorker] Lỗi nghiêm trọng: {fatal_ex}")


def authenticate_tts_step1(username: str, password: str, timeout: int = 15) -> dict:
    """
    Bước 1: Gửi thông tin tài khoản & mật khẩu lên hệ thống CAS TTS qua Dedicated Worker Thread.
    """
    _ensure_worker_started()
    res_q = queue.Queue()
    _JOB_QUEUE.put({
        "action": "step1",
        "args": {"username": username, "password": password, "timeout": timeout},
        "res_q": res_q
    })
    try:
        return res_q.get(timeout=timeout + 10)
    except queue.Empty:
        return {"success": False, "error": "Quá thời gian kết nối tới dịch vụ xác thực máy chủ."}


def authenticate_tts_step2_otp(session_id: str, otp_code: str, timeout: int = 25) -> dict:
    """
    Bước 2: Gửi mã OTP vào phiên CAS đang chờ qua Dedicated Worker Thread.
    """
    _ensure_worker_started()
    res_q = queue.Queue()
    _JOB_QUEUE.put({
        "action": "step2",
        "args": {"session_id": session_id, "otp_code": otp_code, "timeout": timeout},
        "res_q": res_q
    })
    try:
        return res_q.get(timeout=timeout + 10)
    except queue.Empty:
        return {"success": False, "error": "Quá thời gian xử lý mã xác thực OTP từ máy chủ CAS."}
